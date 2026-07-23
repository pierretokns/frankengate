package eventstream

import (
	"bytes"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"hash/crc32"
	"io"
	"reflect"
	"strings"
	"testing"
	"unicode/utf8"
)

type fragmented struct {
	b []byte
	n int
}

func (f *fragmented) Read(p []byte) (int, error) {
	if len(f.b) == 0 {
		return 0, io.EOF
	}
	n := min(f.n, len(p), len(f.b))
	copy(p, f.b[:n])
	f.b = f.b[n:]
	return n, nil
}

func TestRoundTripEveryHeaderTypeWithFragmentedReads(t *testing.T) {
	uuid := [16]byte{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}
	want := Frame{Headers: []Header{
		{Name: "true", Type: HeaderBoolTrue},
		{Name: "false", Type: HeaderBoolFalse},
		{Name: "byte", Type: HeaderByte, Value: int8(-2)},
		{Name: "short", Type: HeaderShort, Value: int16(-3)},
		{Name: "int", Type: HeaderInt, Value: int32(-4)},
		{Name: "long", Type: HeaderLong, Value: int64(-5)},
		{Name: "bytes", Type: HeaderByteArray, Value: []byte{0, 1, 2}},
		{Name: "string", Type: HeaderString, Value: "chunk"},
		{Name: "stamp", Type: HeaderTimestamp, Value: int64(42)},
		{Name: "uuid", Type: HeaderUUID, Value: uuid},
	}, Payload: []byte("hello")}
	encoded, err := Encode(want)
	if err != nil {
		t.Fatal(err)
	}
	got, err := Read(&fragmented{b: encoded, n: 1})
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("round trip mismatch:\n got: %#v\nwant: %#v", got, want)
	}
}

func TestPinnedHandVectorForEmptyFrame(t *testing.T) {
	// Generated independently from the pinned Smithy EventStream field layout:
	// total=16, headers=0, CRC32(prelude), CRC32(message without final CRC).
	const vector = "000000100000000005c248eb7d98c8ff"
	encoded, err := Encode(Frame{})
	if err != nil {
		t.Fatal(err)
	}
	if hex.EncodeToString(encoded) != vector {
		t.Fatalf("encoded = %x, want %s", encoded, vector)
	}
	decoded, err := Read(bytes.NewReader(mustDecodeHex(t, vector)))
	if err != nil {
		t.Fatal(err)
	}
	if len(decoded.Headers) != 0 || len(decoded.Payload) != 0 {
		t.Fatalf("decoded empty vector = %#v", decoded)
	}
}

func TestCRCsFailClosed(t *testing.T) {
	encoded, _ := Encode(Frame{Payload: []byte("x")})
	encoded[8] ^= 1
	if _, err := Read(bytes.NewReader(encoded)); !errors.Is(err, ErrCRC) {
		t.Fatalf("prelude error = %v", err)
	}
	encoded, _ = Encode(Frame{Payload: []byte("x")})
	encoded[len(encoded)-1] ^= 1
	if _, err := Read(bytes.NewReader(encoded)); !errors.Is(err, ErrCRC) {
		t.Fatalf("message error = %v", err)
	}
}

func TestProtocolLimits(t *testing.T) {
	if _, err := Encode(Frame{Payload: make([]byte, maxPayloadLen+1)}); !errors.Is(err, ErrMalformed) {
		t.Fatalf("oversized payload error = %v", err)
	}
	if _, err := Encode(Frame{Headers: []Header{{Name: "x", Type: HeaderString, Value: strings.Repeat("x", maxHeaderValueLen+1)}}}); !errors.Is(err, ErrMalformed) {
		t.Fatalf("oversized string error = %v", err)
	}
	if _, err := Encode(Frame{Headers: []Header{{Name: "x", Type: HeaderByteArray, Value: make([]byte, maxHeaderValueLen+1)}}}); !errors.Is(err, ErrMalformed) {
		t.Fatalf("oversized blob error = %v", err)
	}
	// Aggregate encoded headers may exceed the old uint16 ceiling while staying
	// below the pinned 128 KiB message-header ceiling.
	maxHeaders := []Header{
		{Name: "a", Type: HeaderByteArray, Value: make([]byte, maxHeaderValueLen)},
		{Name: "b", Type: HeaderByteArray, Value: make([]byte, maxHeaderValueLen)},
		{Name: "c", Type: HeaderByteArray, Value: make([]byte, maxHeaderValueLen)},
		{Name: "d", Type: HeaderByteArray, Value: make([]byte, maxHeaderValueLen-16)},
	}
	if _, err := Encode(Frame{Headers: maxHeaders}); err != nil {
		t.Fatalf("exact-limit aggregate headers rejected: %v", err)
	}
	maxHeaders[3].Value = make([]byte, maxHeaderValueLen-15)
	if _, err := Encode(Frame{Headers: maxHeaders}); !errors.Is(err, ErrMalformed) {
		t.Fatalf("aggregate headers above limit error = %v", err)
	}
	// A payload larger than the old 16 MiB cap remains valid under the pinned
	// 24 MiB payload ceiling.
	encoded, err := Encode(Frame{Payload: make([]byte, (16<<20)+1)})
	if err != nil {
		t.Fatalf("spec-valid payload rejected: %v", err)
	}
	if _, err := Read(bytes.NewReader(encoded)); err != nil {
		t.Fatalf("spec-valid payload could not be read: %v", err)
	}
}

func TestDecoderRejectsInvalidHeadersAndDerivedOversizeBeforeRead(t *testing.T) {
	cases := [][]byte{
		append(rawStringHeader([]byte("x"), []byte("a")), rawStringHeader([]byte("x"), []byte("b"))...),
		rawStringHeader([]byte{0xff}, []byte("a")),
		rawStringHeader([]byte("x"), []byte{0xff}),
		rawStringHeader([]byte("x"), nil),
		rawStringHeader([]byte("x"), make([]byte, maxHeaderValueLen+1)),
	}
	for i, headers := range cases {
		frame := frameFromParts(headers, nil)
		if _, err := Read(bytes.NewReader(frame)); !errors.Is(err, ErrMalformed) {
			t.Fatalf("decoder mutation %d error = %v", i, err)
		}
	}

	var prelude [preludeLen]byte
	binary.BigEndian.PutUint32(prelude[0:4], uint32(maxFrameLen))
	binary.BigEndian.PutUint32(prelude[4:8], 0)
	binary.BigEndian.PutUint32(prelude[8:12], crc32.ChecksumIEEE(prelude[:8]))
	if _, err := Read(bytes.NewReader(prelude[:])); !errors.Is(err, ErrMalformed) {
		t.Fatalf("derived oversized payload was not rejected before body read: %v", err)
	}
}

func TestDuplicateAndInvalidUTF8HeadersFailClosed(t *testing.T) {
	cases := []Frame{
		{Headers: []Header{{Name: "x", Type: HeaderString, Value: "a"}, {Name: "x", Type: HeaderString, Value: "b"}}},
		{Headers: []Header{{Name: string([]byte{0xff}), Type: HeaderString, Value: "a"}}},
		{Headers: []Header{{Name: "x", Type: HeaderString, Value: string([]byte{0xff})}}},
		{Headers: []Header{{Name: "x", Type: HeaderString, Value: ""}}},
		{Headers: []Header{{Name: "x", Type: HeaderByteArray, Value: []byte{}}}},
	}
	for i, frame := range cases {
		if _, err := Encode(frame); !errors.Is(err, ErrMalformed) {
			t.Fatalf("case %d error = %v", i, err)
		}
	}
	if !utf8.ValidString("x") {
		t.Fatal("test invariant")
	}
}

func TestMalformedHeaderMutationFailsClosed(t *testing.T) {
	encoded, _ := Encode(Frame{Headers: []Header{{Name: "x", Type: HeaderString, Value: "y"}}})
	encoded[14] = 0xff
	binary.BigEndian.PutUint32(encoded[len(encoded)-4:], crc32.ChecksumIEEE(encoded[:len(encoded)-4]))
	if _, err := Read(bytes.NewReader(encoded)); !errors.Is(err, ErrMalformed) {
		t.Fatalf("unsupported header error = %v", err)
	}
}

func mustDecodeHex(t *testing.T, input string) []byte {
	t.Helper()
	decoded, err := hex.DecodeString(input)
	if err != nil {
		t.Fatal(err)
	}
	return decoded
}

func rawStringHeader(name, value []byte) []byte {
	header := []byte{byte(len(name))}
	header = append(header, name...)
	header = append(header, byte(HeaderString), byte(len(value)>>8), byte(len(value)))
	header = append(header, value...)
	return header
}

func frameFromParts(headers, payload []byte) []byte {
	total := minFrameLen + len(headers) + len(payload)
	frame := make([]byte, total)
	binary.BigEndian.PutUint32(frame[0:4], uint32(total))
	binary.BigEndian.PutUint32(frame[4:8], uint32(len(headers)))
	binary.BigEndian.PutUint32(frame[8:12], crc32.ChecksumIEEE(frame[:8]))
	copy(frame[12:], headers)
	copy(frame[12+len(headers):], payload)
	binary.BigEndian.PutUint32(frame[total-4:], crc32.ChecksumIEEE(frame[:total-4]))
	return frame
}
