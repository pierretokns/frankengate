// Package eventstream provides a small, offline AWS EventStream framing
// primitive for deterministic protocol tests. It does not claim compatibility
// with any AWS service or SDK implementation.
package eventstream

import (
	"encoding/binary"
	"errors"
	"fmt"
	"hash/crc32"
	"io"
)

const (
	preludeLen  = 12 // total length, headers length, prelude CRC
	minFrameLen = 16 // prelude + message CRC
	maxFrameLen = 16 << 20
)

var (
	ErrMalformed = errors.New("malformed eventstream frame")
	ErrCRC       = errors.New("eventstream crc mismatch")
)

type HeaderType byte

const (
	HeaderBoolTrue  HeaderType = 0
	HeaderBoolFalse HeaderType = 1
	HeaderByte      HeaderType = 2
	HeaderShort     HeaderType = 3
	HeaderInt       HeaderType = 4
	HeaderLong      HeaderType = 5
	HeaderByteArray HeaderType = 6
	HeaderString    HeaderType = 7
	HeaderTimestamp HeaderType = 8
	HeaderUUID      HeaderType = 9
)

type Header struct {
	Name  string
	Type  HeaderType
	Value any
}
type Frame struct {
	Headers []Header
	Payload []byte
}

func Encode(f Frame) ([]byte, error) {
	h, err := encodeHeaders(f.Headers)
	if err != nil {
		return nil, err
	}
	total := preludeLen + len(h) + len(f.Payload) + 4
	if total < minFrameLen || total > maxFrameLen || len(h) > 0xffff {
		return nil, fmt.Errorf("%w: invalid frame size", ErrMalformed)
	}
	b := make([]byte, total)
	binary.BigEndian.PutUint32(b[0:4], uint32(total))
	binary.BigEndian.PutUint32(b[4:8], uint32(len(h)))
	binary.BigEndian.PutUint32(b[8:12], crc32.ChecksumIEEE(b[:8]))
	copy(b[12:], h)
	copy(b[12+len(h):], f.Payload)
	binary.BigEndian.PutUint32(b[total-4:], crc32.ChecksumIEEE(b[:total-4]))
	return b, nil
}

// Read reads exactly one frame, even when the underlying reader returns short
// reads. It validates both the prelude and message CRC before returning data.
func Read(r io.Reader) (Frame, error) {
	var p [12]byte
	if _, err := io.ReadFull(r, p[:]); err != nil {
		return Frame{}, err
	}
	total, headersLen := binary.BigEndian.Uint32(p[:4]), binary.BigEndian.Uint32(p[4:8])
	if total < minFrameLen || total > maxFrameLen || headersLen > total-minFrameLen {
		return Frame{}, fmt.Errorf("%w: lengths", ErrMalformed)
	}
	if crc32.ChecksumIEEE(p[:8]) != binary.BigEndian.Uint32(p[8:12]) {
		return Frame{}, ErrCRC
	}
	rest := make([]byte, int(total)-preludeLen)
	if _, err := io.ReadFull(r, rest); err != nil {
		return Frame{}, err
	}
	all := make([]byte, int(total))
	copy(all, p[:])
	copy(all[12:], rest)
	if crc32.ChecksumIEEE(all[:len(all)-4]) != binary.BigEndian.Uint32(all[len(all)-4:]) {
		return Frame{}, ErrCRC
	}
	hs, err := decodeHeaders(all[12 : 12+headersLen])
	if err != nil {
		return Frame{}, err
	}
	payload := append([]byte(nil), all[12+headersLen:len(all)-4]...)
	return Frame{Headers: hs, Payload: payload}, nil
}

func encodeHeaders(hs []Header) ([]byte, error) {
	b := make([]byte, 0)
	for _, h := range hs {
		if len(h.Name) == 0 || len(h.Name) > 255 {
			return nil, fmt.Errorf("%w: header name", ErrMalformed)
		}
		b = append(b, byte(len(h.Name)))
		b = append(b, h.Name...)
		b = append(b, byte(h.Type))
		switch h.Type {
		case HeaderBoolTrue, HeaderBoolFalse:
			if h.Value != nil {
				return nil, fmt.Errorf("%w: bool value", ErrMalformed)
			}
		case HeaderByte:
			v, ok := h.Value.(int8)
			if !ok {
				return nil, fmt.Errorf("%w: byte value", ErrMalformed)
			}
			b = append(b, byte(v))
		case HeaderShort:
			v, ok := h.Value.(int16)
			if !ok {
				return nil, fmt.Errorf("%w: short value", ErrMalformed)
			}
			var x [2]byte
			binary.BigEndian.PutUint16(x[:], uint16(v))
			b = append(b, x[:]...)
		case HeaderInt:
			v, ok := h.Value.(int32)
			if !ok {
				return nil, fmt.Errorf("%w: int value", ErrMalformed)
			}
			var x [4]byte
			binary.BigEndian.PutUint32(x[:], uint32(v))
			b = append(b, x[:]...)
		case HeaderLong, HeaderTimestamp:
			v, ok := h.Value.(int64)
			if !ok {
				return nil, fmt.Errorf("%w: long value", ErrMalformed)
			}
			var x [8]byte
			binary.BigEndian.PutUint64(x[:], uint64(v))
			b = append(b, x[:]...)
		case HeaderString:
			v, ok := h.Value.(string)
			if !ok || len(v) > 65535 {
				return nil, fmt.Errorf("%w: string value", ErrMalformed)
			}
			var x [2]byte
			binary.BigEndian.PutUint16(x[:], uint16(len(v)))
			b = append(b, x[:]...)
			b = append(b, v...)
		default:
			return nil, fmt.Errorf("%w: unsupported header type %d", ErrMalformed, h.Type)
		}
	}
	return b, nil
}

func decodeHeaders(b []byte) ([]Header, error) {
	var out []Header
	for len(b) > 0 {
		if len(b) < 2 {
			return nil, ErrMalformed
		}
		n := int(b[0])
		b = b[1:]
		if n == 0 || len(b) < n+1 {
			return nil, ErrMalformed
		}
		name := string(b[:n])
		typ := HeaderType(b[n])
		b = b[n+1:]
		var v any
		switch typ {
		case HeaderBoolTrue:
			v = nil
		case HeaderBoolFalse:
			v = nil
		case HeaderByte:
			if len(b) < 1 {
				return nil, ErrMalformed
			}
			v = int8(b[0])
			b = b[1:]
		case HeaderShort:
			if len(b) < 2 {
				return nil, ErrMalformed
			}
			v = int16(binary.BigEndian.Uint16(b))
			b = b[2:]
		case HeaderInt:
			if len(b) < 4 {
				return nil, ErrMalformed
			}
			v = int32(binary.BigEndian.Uint32(b))
			b = b[4:]
		case HeaderLong, HeaderTimestamp:
			if len(b) < 8 {
				return nil, ErrMalformed
			}
			v = int64(binary.BigEndian.Uint64(b))
			b = b[8:]
		case HeaderString:
			if len(b) < 2 {
				return nil, ErrMalformed
			}
			n := int(binary.BigEndian.Uint16(b))
			b = b[2:]
			if len(b) < n {
				return nil, ErrMalformed
			}
			v = string(b[:n])
			b = b[n:]
		default:
			return nil, fmt.Errorf("%w: unsupported header type %d", ErrMalformed, typ)
		}
		out = append(out, Header{Name: name, Type: typ, Value: v})
	}
	return out, nil
}
