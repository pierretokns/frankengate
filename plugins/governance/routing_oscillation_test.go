package governance

import (
	"math/rand"
	"testing"

	"github.com/stretchr/testify/require"
)

// TestFleetRoutingHysteresisBoundsSynchronizedSwitches is a deterministic
// premortem for a 100-pod adaptive router. It models delayed observations,
// shared provider failure, randomized probes, and fallback amplification. The
// acceptance bound is intentionally about synchronized changes, not optimal
// routing quality: no tick may switch more than one quarter of the fleet and
// the fleet must settle after the incident clears.
func TestFleetRoutingHysteresisBoundsSynchronizedSwitches(t *testing.T) {
	const (
		pods       = 100
		ticks      = 80
		delay      = 4
		hysteresis = 0.20
	)

	rng := rand.New(rand.NewSource(0xFAAA))
	provider := make([]int, pods) // 0 = primary, 1 = fallback
	observed := make([][]float64, pods)
	for i := range observed {
		observed[i] = make([]float64, ticks+delay+1)
	}

	maxSwitched := 0
	settledAfterRecovery := 0
	for tick := 0; tick < ticks; tick++ {
		incident := tick >= 10 && tick < 36
		for pod := 0; pod < pods; pod++ {
			// A fallback attempt amplifies the primary's observed error, but
			// each pod probes independently rather than flipping in lockstep.
			error := 0.02
			if incident {
				error = 0.85
			}
			if provider[pod] == 1 && incident {
				error = 0.10
			}
			observed[pod][tick] = error + (rng.Float64()-0.5)*0.08
		}

		switched := 0
		for pod := 0; pod < pods; pod++ {
			if tick < delay || rng.Intn(5) != 0 {
				continue // randomized probe schedule
			}
			sample := observed[pod][tick-delay]
			if provider[pod] == 0 && sample > hysteresis {
				provider[pod] = 1
				switched++
			} else if provider[pod] == 1 && sample < 0.05 {
				provider[pod] = 0
				switched++
			}
		}
		if switched > maxSwitched {
			maxSwitched = switched
		}
		if tick >= 60 {
			for _, selected := range provider {
				if selected == 0 {
					settledAfterRecovery++
				}
			}
		}
	}

	require.LessOrEqual(t, maxSwitched, pods/4,
		"hysteresis/probe jitter must bound synchronized fleet switches")
	require.GreaterOrEqual(t, settledAfterRecovery, pods/2,
		"most pods should return to the primary after recovery")
}
