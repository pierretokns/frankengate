package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"os"
	"strings"
	"sync"
	"time"
)

type event struct {
	Schema         string    `json:"schema"`
	ObservedAt     time.Time `json:"observed_at"`
	RunID          string    `json:"run_id"`
	Source         string    `json:"source"`
	Destination    string    `json:"destination"`
	Family         string    `json:"family"`
	Transport      string    `json:"transport"`
	Port           string    `json:"port"`
	Classification string    `json:"classification"`
	Bytes          int       `json:"bytes"`
}

type listenSpec struct {
	Network string
	Address string
}

func listenerSpecifications() (tcp []listenSpec, udp []listenSpec) {
	for _, port := range []string{"80", "443", "3128", "8080"} {
		tcp = append(tcp,
			listenSpec{Network: "tcp4", Address: "0.0.0.0:" + port},
			listenSpec{Network: "tcp6", Address: "[::]:" + port},
		)
	}
	for _, port := range []string{"53", "443"} {
		udp = append(udp,
			listenSpec{Network: "udp4", Address: "0.0.0.0:" + port},
			listenSpec{Network: "udp6", Address: "[::]:" + port},
		)
	}
	return tcp, udp
}

func main() {
	var runID string
	flag.StringVar(&runID, "run-id", "", "sealed lab run identifier")
	flag.Parse()
	if runID == "" {
		fmt.Fprintln(os.Stderr, "egress-sentinel requires -run-id")
		os.Exit(2)
	}
	encoder := json.NewEncoder(os.Stdout)
	var outputMu sync.Mutex
	emit := func(item event) {
		outputMu.Lock()
		defer outputMu.Unlock()
		_ = encoder.Encode(item)
	}
	var wait sync.WaitGroup
	tcpSpecs, udpSpecs := listenerSpecifications()
	for _, spec := range tcpSpecs {
		listener, err := net.Listen(spec.Network, spec.Address)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		wait.Add(1)
		go acceptTCP(listener, runID, emit, &wait)
	}
	for _, spec := range udpSpecs {
		packet, err := net.ListenPacket(spec.Network, spec.Address)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		wait.Add(1)
		go acceptUDP(packet, runID, emit, &wait)
	}
	wait.Wait()
}

func acceptTCP(listener net.Listener, runID string, emit func(event), wait *sync.WaitGroup) {
	defer wait.Done()
	for {
		connection, err := listener.Accept()
		if err != nil {
			return
		}
		buffer := make([]byte, 4096)
		_ = connection.SetReadDeadline(time.Now().Add(250 * time.Millisecond))
		read, _ := connection.Read(buffer)
		emit(newEvent(runID, connection.RemoteAddr(), connection.LocalAddr(), "tcp", read))
		_ = connection.Close()
	}
}

func acceptUDP(packet net.PacketConn, runID string, emit func(event), wait *sync.WaitGroup) {
	defer wait.Done()
	buffer := make([]byte, 4096)
	for {
		read, source, err := packet.ReadFrom(buffer)
		if err != nil {
			return
		}
		emit(newEvent(runID, source, packet.LocalAddr(), "udp", read))
	}
}

func newEvent(runID string, source, destination net.Addr, transport string, bytes int) event {
	family := "ipv4"
	if strings.Contains(source.String(), "[") || strings.Count(source.String(), ":") > 1 {
		family = "ipv6"
	}
	_, port, _ := net.SplitHostPort(destination.String())
	return event{
		Schema: "sealed-lab-egress-event/v1", ObservedAt: time.Now().UTC(), RunID: runID,
		Source: source.String(), Destination: destination.String(), Family: family,
		Transport: transport, Port: port, Classification: "forbidden-egress-attempt", Bytes: bytes,
	}
}
