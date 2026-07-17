package handlers

import "testing"

func TestValidAlertChannelType(t *testing.T) {
	for _, kind := range []string{"webhook", "SNS", "email"} {
		if !validAlertChannelType(kind) {
			t.Fatalf("expected channel type %q to be accepted", kind)
		}
	}
	for _, kind := range []string{"", "slack", "pagerduty"} {
		if validAlertChannelType(kind) {
			t.Fatalf("expected channel type %q to be rejected", kind)
		}
	}
}
