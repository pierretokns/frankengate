package main

import (
	"net"
	"reflect"
	"testing"
)

type testAddr string

func (address testAddr) Network() string { return "test" }
func (address testAddr) String() string  { return string(address) }

func TestEgressEventsClassifyBothAddressFamilies(t *testing.T) {
	tests := []struct {
		source, destination string
		family              string
	}{
		{"172.30.10.10:1234", "172.30.10.254:443", "ipv4"},
		{"[fd00:bf:10::10]:1234", "[fd00:bf:10::fe]:443", "ipv6"},
	}
	for _, test := range tests {
		item := newEvent("run-1", testAddr(test.source), testAddr(test.destination), "udp", 7)
		if item.Schema != "sealed-lab-egress-event/v1" || item.Classification != "forbidden-egress-attempt" || item.Family != test.family || item.Port != "443" || item.Bytes != 7 {
			t.Fatalf("unexpected event: %#v", item)
		}
	}
}

func TestListenerSpecificationsAreExplicitlyDualStack(t *testing.T) {
	tcp, udp := listenerSpecifications()
	wantTCP := []listenSpec{
		{Network: "tcp4", Address: "0.0.0.0:80"}, {Network: "tcp6", Address: "[::]:80"},
		{Network: "tcp4", Address: "0.0.0.0:443"}, {Network: "tcp6", Address: "[::]:443"},
		{Network: "tcp4", Address: "0.0.0.0:3128"}, {Network: "tcp6", Address: "[::]:3128"},
		{Network: "tcp4", Address: "0.0.0.0:8080"}, {Network: "tcp6", Address: "[::]:8080"},
	}
	wantUDP := []listenSpec{
		{Network: "udp4", Address: "0.0.0.0:53"}, {Network: "udp6", Address: "[::]:53"},
		{Network: "udp4", Address: "0.0.0.0:443"}, {Network: "udp6", Address: "[::]:443"},
	}
	if !reflect.DeepEqual(tcp, wantTCP) || !reflect.DeepEqual(udp, wantUDP) {
		t.Fatalf("listener matrix drifted: tcp=%v udp=%v", tcp, udp)
	}
}

func TestSentinelEventNeverClassifiesTrafficAsPaidInference(t *testing.T) {
	item := newEvent("run-1", &net.TCPAddr{IP: net.ParseIP("172.30.10.10"), Port: 1234}, &net.TCPAddr{IP: net.ParseIP("172.30.10.254"), Port: 443}, "tcp", 0)
	if item.Classification != "forbidden-egress-attempt" {
		t.Fatalf("unexpected classification: %s", item.Classification)
	}
}
