package eventstream

import (
	"bytes"
	"encoding/binary"
	"errors"
	"hash/crc32"
	"io"
	"testing"
)

type fragmented struct {
	b []byte
	n int
}

func (f *fragmented) Read(p []byte) (int, error) {
	if len(f.b) == 0 {
		return 0, io.EOF
	}
	n := f.n
	if n > len(p) {
		n = len(p)
	}
	if n > len(f.b) {
		n = len(f.b)
	}
	copy(p, f.b[:n])
	f.b = f.b[n:]
	return n, nil
}

func TestRoundTripWithTypedHeaders(t *testing.T) {
	want := Frame{Headers: []Header{{"event-type", HeaderString, "chunk"}, {"status", HeaderInt, int32(200)}, {"ok", HeaderBoolTrue, nil}, {"stamp", HeaderTimestamp, int64(42)}}, Payload: []byte("hello")}
	b, err := Encode(want)
	if err != nil {
		t.Fatal(err)
	}
	got, err := Read(&fragmented{b: b, n: 1})
	if err != nil {
		t.Fatal(err)
	}
	if string(got.Payload) != "hello" || len(got.Headers) != 4 || got.Headers[1].Value != int32(200) {
		t.Fatalf("unexpected frame: %#v", got)
	}
}

func TestCRCsFailClosed(t *testing.T) {
	b, _ := Encode(Frame{Payload: []byte("x")})
	b[8] ^= 1
	if _, err := Read(bytes.NewReader(b)); !errors.Is(err, ErrCRC) {
		t.Fatalf("prelude error=%v", err)
	}
	b, _ = Encode(Frame{Payload: []byte("x")})
	b[len(b)-1] ^= 1
	if _, err := Read(bytes.NewReader(b)); !errors.Is(err, ErrCRC) {
		t.Fatalf("message error=%v", err)
	}
}

func TestMalformedAndUnsupportedHeaders(t *testing.T) {
	if _, err := Encode(Frame{Headers: []Header{{Name: "x", Type: HeaderUUID, Value: nil}}}); !errors.Is(err, ErrMalformed) {
		t.Fatalf("expected malformed, got %v", err)
	}
	b, _ := Encode(Frame{Headers: []Header{{Name: "x", Type: HeaderString, Value: "y"}}})
	b[14] = 0xff // mutate type, preserve valid framing
	// header mutation is intentionally detected as an unsupported type, not CRC.
	imported := b[:len(b)-4]
	binary.BigEndian.PutUint32(b[len(b)-4:], crc32.ChecksumIEEE(imported))
	if _, err := Read(bytes.NewReader(b)); !errors.Is(err, ErrMalformed) {
		t.Fatalf("expected unsupported header, got %v", err)
	}
}
