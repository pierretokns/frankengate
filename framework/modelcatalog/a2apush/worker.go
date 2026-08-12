package a2apush

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"
)

const defaultMaxPayloadBytes = 1 << 20

type PayloadSource interface {
	Load(context.Context, string) ([]byte, error)
}

type PayloadSourceFunc func(context.Context, string) ([]byte, error)

func (f PayloadSourceFunc) Load(ctx context.Context, ref string) ([]byte, error) {
	return f(ctx, ref)
}

type Worker struct {
	Outbox          OutboxStore
	Configs         Store
	Payloads        PayloadSource
	Delivery        Delivery
	Policy          Policy
	Now             func() time.Time
	Lease           time.Duration
	RetryAfter      time.Duration
	MaxAttempts     int
	MaxPayloadBytes int
	Observer        Observer
}

type WorkerStats struct {
	Claimed    int
	Delivered  int
	Retried    int
	DeadLetter int
	Skipped    int
}

// RunOnce processes due records for one tenant. The Delivery implementation is
// injected so deployments can choose their egress client, while this worker
// owns durable state, bounded payload loading, and retry/dead-letter
// transitions.
func (w Worker) RunOnce(ctx context.Context, tenant string) (WorkerStats, error) {
	var stats WorkerStats
	if w.Outbox == nil || w.Configs == nil || w.Payloads == nil || w.Delivery == nil {
		return stats, ErrDisabled
	}
	if strings.TrimSpace(tenant) == "" {
		return stats, errors.New("A2A push worker tenant is required")
	}
	now := time.Now()
	if w.Now != nil {
		now = w.Now()
	}
	lease := w.Lease
	if lease <= 0 {
		lease = time.Minute
	}
	retryAfter := w.RetryAfter
	if retryAfter <= 0 {
		retryAfter = time.Second
	}
	maxAttempts := w.MaxAttempts
	if maxAttempts <= 0 {
		maxAttempts = 3
	}
	maxPayloadBytes := w.MaxPayloadBytes
	if maxPayloadBytes <= 0 {
		maxPayloadBytes = defaultMaxPayloadBytes
	}
	records, err := w.Outbox.List(ctx, tenant)
	if err != nil {
		return stats, err
	}
	for _, record := range records {
		if record.Status == DeliveryDelivered || record.Status == DeliveryDeadLetter || record.NextAttempt.After(now) || (record.Status == DeliveryInFlight && record.LeaseUntil.After(now)) {
			stats.Skipped++
			continue
		}
		claimed, err := w.Outbox.Claim(ctx, record.TenantID, record.TaskID, record.ID, now, lease)
		if err != nil {
			if errors.Is(err, ErrOutboxConflict) {
				stats.Skipped++
				continue
			}
			return stats, err
		}
		stats.Claimed++
		cfg, err := w.Configs.Get(ctx, claimed.TenantID, claimed.TaskID, claimed.ConfigID)
		if err == nil {
			if policyErr := ValidateConfig(ctx, cfg, w.Policy); policyErr != nil {
				err = fmt.Errorf("validate A2A push destination: %w", policyErr)
			}
		}
		if err == nil {
			payload, loadErr := w.Payloads.Load(ctx, claimed.PayloadRef)
			if loadErr != nil {
				err = fmt.Errorf("load A2A push payload: %w", loadErr)
			} else if len(payload) > maxPayloadBytes {
				err = fmt.Errorf("A2A push payload exceeds %d bytes", maxPayloadBytes)
			} else if PayloadDigest(payload) != claimed.PayloadHash {
				err = errors.New("A2A push payload digest mismatch")
			} else {
				err = w.Delivery.Deliver(ctx, DeliveryRequest{
					Config:      cfg,
					Payload:     append([]byte(nil), payload...),
					DeliveryID:  claimed.ID,
					PayloadHash: claimed.PayloadHash,
					Attempt:     claimed.Attempts,
				})
			}
		}
		if err == nil {
			if completeErr := w.Outbox.Complete(ctx, claimed.TenantID, claimed.TaskID, claimed.ID, now); completeErr != nil {
				return stats, completeErr
			}
			stats.Delivered++
			notifyObserver(w.Observer, ctx, Observation{Outcome: "delivered", Status: DeliveryDelivered})
			continue
		}
		failed, failErr := w.Outbox.Fail(ctx, claimed.TenantID, claimed.TaskID, claimed.ID, now, retryAfter, maxAttempts, err)
		if failErr != nil {
			return stats, failErr
		}
		if failed.Status == DeliveryDeadLetter {
			stats.DeadLetter++
			notifyObserver(w.Observer, ctx, Observation{Outcome: "dead_letter", Status: failed.Status, ErrorClass: deliveryErrorClass(err)})
		} else {
			stats.Retried++
			notifyObserver(w.Observer, ctx, Observation{Outcome: "retry", Status: failed.Status, ErrorClass: deliveryErrorClass(err)})
		}
	}
	return stats, nil
}

func deliveryErrorClass(err error) string {
	if err == nil {
		return "unknown"
	}
	message := strings.ToLower(err.Error())
	switch {
	case strings.Contains(message, "payload"):
		return "payload"
	case strings.Contains(message, "credential"), strings.Contains(message, "secret"):
		return "credential"
	case strings.Contains(message, "dns"), strings.Contains(message, "destination"):
		return "destination"
	case strings.Contains(message, "timeout"), strings.Contains(message, "context"):
		return "timeout"
	default:
		return "delivery"
	}
}

func notifyObserver(observer Observer, ctx context.Context, observation Observation) {
	if observer == nil {
		return
	}
	defer func() { _ = recover() }()
	observer.ObserveA2APush(ctx, observation)
}
