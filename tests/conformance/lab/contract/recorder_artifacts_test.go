package contract

import (
	"bytes"
	"encoding/binary"
	"strconv"
	"strings"
	"testing"
)

func recorderPCAPNGTestBlock(order binary.ByteOrder, blockType uint32, body []byte) []byte {
	length := uint32(12 + len(body))
	block := make([]byte, length)
	order.PutUint32(block[0:4], blockType)
	order.PutUint32(block[4:8], length)
	copy(block[8:len(block)-4], body)
	order.PutUint32(block[len(block)-4:], length)
	return block
}

func appendRecorderPCAPNGTestOption(options []byte, order binary.ByteOrder, code uint16, value []byte) []byte {
	paddedLength := (len(value) + 3) &^ 3
	start := len(options)
	options = append(options, make([]byte, 4+paddedLength)...)
	order.PutUint16(options[start:start+2], code)
	order.PutUint16(options[start+2:start+4], uint16(len(value)))
	copy(options[start+4:start+4+len(value)], value)
	return options
}

func recorderPCAPNGTestBlocks(t *testing.T, order binary.ByteOrder) [][]byte {
	t.Helper()
	expected := validRecorderExpectations(t)
	section := make([]byte, 16)
	order.PutUint32(section[0:4], pcapngByteOrderMagic)
	order.PutUint16(section[4:6], 1)
	order.PutUint16(section[6:8], 0)
	order.PutUint64(section[8:16], ^uint64(0))
	blocks := [][]byte{recorderPCAPNGTestBlock(order, pcapngSectionHeaderBlock, section)}
	for _, bridge := range expected.Bridges {
		body := make([]byte, 8)
		order.PutUint16(body[0:2], pcapngEthernetLinkType)
		order.PutUint32(body[4:8], 65535)
		options := appendRecorderPCAPNGTestOption(nil, order, pcapngIfNameOption, []byte(bridge.Name))
		options = appendRecorderPCAPNGTestOption(options, order, pcapngIfDescriptionOption, []byte("linux-ifindex="+strconv.FormatUint(uint64(bridge.IfIndex), 10)))
		options = appendRecorderPCAPNGTestOption(options, order, pcapngIfTimestampResolution, []byte{9})
		options = append(options, 0, 0, 0, 0)
		body = append(body, options...)
		blocks = append(blocks, recorderPCAPNGTestBlock(order, pcapngInterfaceDescription, body))
	}
	for interfaceID, bridge := range expected.Bridges {
		for markerIndex, marker := range []string{RecorderCalibrationStart, RecorderCalibrationEnd} {
			packet, err := RecorderCalibrationFrame(expected.InvocationNonce, bridge.Role, marker)
			if err != nil {
				t.Fatal(err)
			}
			timestamp := uint64(90)
			if markerIndex == 1 {
				timestamp = 1050
			}
			body := make([]byte, 20)
			order.PutUint32(body[0:4], uint32(interfaceID))
			order.PutUint32(body[4:8], uint32(timestamp>>32))
			order.PutUint32(body[8:12], uint32(timestamp))
			order.PutUint32(body[12:16], uint32(len(packet)))
			order.PutUint32(body[16:20], uint32(len(packet)))
			body = append(body, packet...)
			blocks = append(blocks, recorderPCAPNGTestBlock(order, pcapngEnhancedPacket, body))
		}
	}
	for interfaceID := uint32(0); interfaceID < 3; interfaceID++ {
		body := make([]byte, 12)
		order.PutUint32(body[0:4], interfaceID)
		order.PutUint32(body[4:8], 0)
		order.PutUint32(body[8:12], 1100)
		options := make([]byte, 0, 64)
		for _, option := range []struct {
			code  uint16
			value uint64
		}{
			{pcapngISBStartTimeOption, 80}, {pcapngISBEndTimeOption, 1100}, {pcapngISBIfRecvOption, 2},
			{pcapngISBIfDropOption, 0}, {pcapngISBOSDropOption, 0},
		} {
			value := make([]byte, 8)
			order.PutUint64(value, option.value)
			options = appendRecorderPCAPNGTestOption(options, order, option.code, value)
		}
		options = append(options, 0, 0, 0, 0)
		body = append(body, options...)
		blocks = append(blocks, recorderPCAPNGTestBlock(order, pcapngInterfaceStatistics, body))
	}
	return blocks
}

func joinRecorderPCAPNGBlocks(blocks [][]byte) []byte {
	return bytes.Join(blocks, nil)
}

func recorderArtifactTranscript(t *testing.T, pcapng []byte, ledgerOverride []byte) (RecorderTranscript, []byte) {
	t.Helper()
	records := validRecorderTranscript(t)
	last := len(records) - 1
	ledger, err := recorderLedgerBytes(records[:last])
	if err != nil {
		t.Fatal(err)
	}
	if ledgerOverride != nil {
		ledger = ledgerOverride
	}
	records[last].Manifest.Artifacts[0].SHA256 = SHA256Hex(pcapng)
	records[last].Manifest.Artifacts[0].SizeBytes = uint64(len(pcapng))
	records[last].Manifest.Artifacts[1].SHA256 = SHA256Hex(ledger)
	records[last].Manifest.Artifacts[1].SizeBytes = uint64(len(ledger))
	for index := range records[last].Manifest.Interfaces {
		records[last].Manifest.Interfaces[index].Packets = 2
		records[last].Manifest.Interfaces[index].DroppedPackets = 0
		records[last].Manifest.Interfaces[index].TruncatedPackets = 0
	}
	records = resealRecorderRecords(t, records)
	transcript, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, records)), validRecorderExpectations(t))
	if err != nil {
		t.Fatalf("decode artifact transcript: %v", err)
	}
	return *transcript, ledger
}

func TestVerifyRecorderArtifactsBothByteOrders(t *testing.T) {
	for _, test := range []struct {
		name  string
		order binary.ByteOrder
	}{{"little", binary.LittleEndian}, {"big", binary.BigEndian}} {
		t.Run(test.name, func(t *testing.T) {
			pcapng := joinRecorderPCAPNGBlocks(recorderPCAPNGTestBlocks(t, test.order))
			transcript, ledger := recorderArtifactTranscript(t, pcapng, nil)
			if err := VerifyRecorderArtifacts(transcript, validRecorderExpectations(t), pcapng, ledger); err != nil {
				t.Fatalf("valid artifacts rejected: %v", err)
			}
		})
	}
}

func TestRecorderCalibrationFrameGolden(t *testing.T) {
	frame, err := RecorderCalibrationFrame(strings.Repeat("a", 64), "client_net", RecorderCalibrationStart)
	if err != nil {
		t.Fatal(err)
	}
	want := append([]byte{0x02, 0x46, 0x47, 0x00, 0x00, 0x01, 0x02, 0x46, 0x47, 0x00, 0x00, 0x02, 0x88, 0xb5}, []byte("fgcal1|client_net|start|1d71af28c216b759fdbf  ")...)
	if !bytes.Equal(frame, want) || len(frame) != 60 {
		t.Fatalf("calibration frame changed: %x", frame)
	}
	for _, invalid := range [][3]string{
		{"bad", "client_net", RecorderCalibrationStart},
		{strings.Repeat("a", 64), "wrong_net", RecorderCalibrationStart},
		{strings.Repeat("a", 64), "client_net", "middle"},
	} {
		if _, err := RecorderCalibrationFrame(invalid[0], invalid[1], invalid[2]); err == nil {
			t.Fatal("invalid calibration identity accepted")
		}
	}
}

func TestVerifyRecorderArtifactHashesSizesAndCanonicalLedger(t *testing.T) {
	pcapng := joinRecorderPCAPNGBlocks(recorderPCAPNGTestBlocks(t, binary.LittleEndian))
	transcript, ledger := recorderArtifactTranscript(t, pcapng, nil)
	if err := VerifyRecorderArtifacts(transcript, validRecorderExpectations(t), append(pcapng, 0), ledger); err == nil {
		t.Fatal("pcapng size/hash substitution accepted")
	}
	if err := VerifyRecorderArtifacts(transcript, validRecorderExpectations(t), pcapng, append(ledger, 0)); err == nil {
		t.Fatal("ledger size/hash substitution accepted")
	}
	forgedCounters := transcript
	forgedCounters.Records = append([]RecorderRecord(nil), transcript.Records...)
	last := len(forgedCounters.Records) - 1
	manifestCopy := *forgedCounters.Records[last].Manifest
	manifestCopy.Interfaces = append([]RecorderInterfaceCounter(nil), manifestCopy.Interfaces...)
	manifestCopy.Interfaces[0].Packets++
	forgedCounters.Records[last].Manifest = &manifestCopy
	forgedCounters.Records = resealRecorderRecords(t, forgedCounters.Records)
	if err := VerifyRecorderArtifacts(forgedCounters, validRecorderExpectations(t), pcapng, ledger); err == nil {
		t.Fatal("forged manifest packet counter accepted")
	}

	forgedLedger := append(append([]byte(nil), ledger...), []byte("{}\n")...)
	forgedTranscript, _ := recorderArtifactTranscript(t, pcapng, forgedLedger)
	if err := VerifyRecorderArtifacts(forgedTranscript, validRecorderExpectations(t), pcapng, forgedLedger); err == nil {
		t.Fatal("manifest-matching forged ledger accepted")
	}

	canonical, err := recorderLedgerBytes(transcript.Records[:len(transcript.Records)-1])
	if err != nil || !bytes.Equal(canonical, ledger) || !bytes.HasSuffix(ledger, []byte("\n")) {
		t.Fatalf("canonical ledger mismatch: err=%v", err)
	}
	if bytes.Contains(ledger, []byte(`"type":"FINALIZED"`)) {
		t.Fatal("canonical ledger circularly includes FINALIZED")
	}
}

func TestRecorderPCAPNGMutationsFailClosed(t *testing.T) {
	validBlocks := func() [][]byte { return recorderPCAPNGTestBlocks(t, binary.LittleEndian) }
	mutations := map[string]func() []byte{
		"bad byte order magic": func() []byte {
			blocks := validBlocks()
			blocks[0][8] ^= 1
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"section options": func() []byte {
			blocks := validBlocks()
			body := append([]byte(nil), blocks[0][8:len(blocks[0])-4]...)
			body = append(body, 0, 0, 0, 0)
			blocks[0] = recorderPCAPNGTestBlock(binary.LittleEndian, pcapngSectionHeaderBlock, body)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"bad section trailer": func() []byte {
			blocks := validBlocks()
			blocks[0][len(blocks[0])-1] ^= 1
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"wrong interface name": func() []byte {
			blocks := validBlocks()
			index := bytes.Index(blocks[1], []byte(validRecorderExpectations(t).Bridges[0].Name))
			blocks[1][index] ^= 1
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"wrong Linux ifindex": func() []byte {
			blocks := validBlocks()
			index := bytes.Index(blocks[1], []byte("linux-ifindex=11"))
			blocks[1][index+len("linux-ifindex=")] = '9'
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"microsecond default forbidden": func() []byte {
			blocks := validBlocks()
			pattern := []byte{byte(pcapngIfTimestampResolution), 0, 1, 0, 9, 0, 0, 0}
			index := bytes.Index(blocks[1], pattern)
			if index < 0 {
				t.Fatal("test IDB omitted timestamp resolution option")
			}
			blocks[1][index+4] = 6
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"non ethernet": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint16(blocks[1][8:10], 101)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"unknown IDB option": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint16(blocks[1][16:18], 3)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"duplicate IDB option": func() []byte {
			blocks := validBlocks()
			nameOptionLength := 4 + ((len(validRecorderExpectations(t).Bridges[0].Name) + 3) &^ 3)
			binary.LittleEndian.PutUint16(blocks[1][16+nameOptionLength:18+nameOptionLength], pcapngIfNameOption)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"bad IDB trailer": func() []byte {
			blocks := validBlocks()
			blocks[1][len(blocks[1])-1] ^= 1
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"missing IDB": func() []byte {
			blocks := validBlocks()
			blocks = append(blocks[:3], blocks[4:]...)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"unknown block": func() []byte {
			blocks := validBlocks()
			blocks = append(blocks, recorderPCAPNGTestBlock(binary.LittleEndian, 5, nil))
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"unknown interface id": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint32(blocks[4][8:12], 3)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"truncated packet": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint32(blocks[4][24:28], 15)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"sub-Ethernet packet": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint32(blocks[4][20:24], 59)
			binary.LittleEndian.PutUint32(blocks[4][24:28], 59)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"zero timestamp": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint32(blocks[4][12:16], 0)
			binary.LittleEndian.PutUint32(blocks[4][16:20], 0)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"regressing timestamp": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint32(blocks[5][16:20], 50)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"start after READY": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint32(blocks[4][16:20], 101)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"end before teardown": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint32(blocks[5][16:20], 899)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"zero packet": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint32(blocks[4][20:24], 0)
			binary.LittleEndian.PutUint32(blocks[4][24:28], 0)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"EPB options": func() []byte {
			blocks := validBlocks()
			body := append([]byte(nil), blocks[4][8:len(blocks[4])-4]...)
			body = append(body, 0, 0, 0, 0)
			blocks[4] = recorderPCAPNGTestBlock(binary.LittleEndian, pcapngEnhancedPacket, body)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"nonzero packet padding": func() []byte {
			blocks := validBlocks()
			body := append([]byte(nil), blocks[4][8:len(blocks[4])-4]...)
			body = append(body, 0, 0, 0, 1)
			binary.LittleEndian.PutUint32(body[12:16], 61)
			binary.LittleEndian.PutUint32(body[16:20], 61)
			blocks[4] = recorderPCAPNGTestBlock(binary.LittleEndian, pcapngEnhancedPacket, body)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"mutated start calibration": func() []byte {
			blocks := validBlocks()
			blocks[4][28] ^= 1
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"mutated end calibration": func() []byte {
			blocks := validBlocks()
			blocks[5][28] ^= 1
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"duplicate start calibration": func() []byte {
			blocks := validBlocks()
			duplicate := append([]byte(nil), blocks[4]...)
			blocks = append(blocks[:5], append([][]byte{duplicate}, blocks[5:]...)...)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"packet count mismatch": func() []byte {
			blocks := validBlocks()
			packet := bytes.Repeat([]byte{7}, 60)
			body := make([]byte, 20)
			binary.LittleEndian.PutUint32(body[0:4], 0)
			binary.LittleEndian.PutUint32(body[8:12], 500)
			binary.LittleEndian.PutUint32(body[12:16], uint32(len(packet)))
			binary.LittleEndian.PutUint32(body[16:20], uint32(len(packet)))
			body = append(body, packet...)
			extra := recorderPCAPNGTestBlock(binary.LittleEndian, pcapngEnhancedPacket, body)
			blocks = append(blocks[:5], append([][]byte{extra}, blocks[5:]...)...)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"missing ISB": func() []byte {
			blocks := validBlocks()
			blocks = append(blocks[:10], blocks[11:]...)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"duplicate ISB": func() []byte {
			blocks := validBlocks()
			duplicate := append([]byte(nil), blocks[10]...)
			blocks = append(blocks[:11], append([][]byte{duplicate}, blocks[11:]...)...)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"missing ISB option": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint16(blocks[10][20:22], pcapngISBEndTimeOption)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"duplicate ISB option": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint16(blocks[10][32:34], pcapngISBStartTimeOption)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"forged ifrecv": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint64(blocks[10][48:56], 3)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"forged ifdrop": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint64(blocks[10][60:68], 1)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"forged osdrop": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint64(blocks[10][72:80], 1)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"ISB starts after calibration": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint64(blocks[10][24:32], 91)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"ISB ends after FINALIZED": func() []byte {
			blocks := validBlocks()
			binary.LittleEndian.PutUint32(blocks[10][16:20], 1300)
			binary.LittleEndian.PutUint64(blocks[10][36:44], 1300)
			return joinRecorderPCAPNGBlocks(blocks)
		},
		"trailing bytes": func() []byte {
			return append(joinRecorderPCAPNGBlocks(validBlocks()), 0)
		},
		"truncated block": func() []byte {
			data := joinRecorderPCAPNGBlocks(validBlocks())
			return data[:len(data)-1]
		},
	}
	for name, mutate := range mutations {
		t.Run(name, func(t *testing.T) {
			pcapng := mutate()
			transcript, ledger := recorderArtifactTranscript(t, pcapng, nil)
			if err := VerifyRecorderArtifacts(transcript, validRecorderExpectations(t), pcapng, ledger); err == nil {
				t.Fatal("forged or malformed pcapng accepted")
			}
		})
	}
}

func TestAbortedManifestMayReportBoundedLosses(t *testing.T) {
	full := validRecorderTranscript(t)
	abort := RecorderRecord{
		Schema: RecorderControlSchema, Type: RecorderRecordPhase, RunID: "run-1", InvocationNonce: strings.Repeat("a", 64),
		Ordinal: 2, MonotonicNS: 200, Phase: RecorderOutcomeAborted,
		Failure: &RecorderFailure{Code: "capture_failed", Message: "synthetic failure"},
	}
	finalized := full[len(full)-1]
	finalized.Ordinal, finalized.MonotonicNS, finalized.Outcome = 3, 300, RecorderOutcomeAborted
	for index := range finalized.Manifest.Interfaces {
		finalized.Manifest.Interfaces[index].Packets = 0
		finalized.Manifest.Interfaces[index].DroppedPackets = uint64(index + 1)
		finalized.Manifest.Interfaces[index].TruncatedPackets = uint64(index + 2)
	}
	records := resealRecorderRecords(t, []RecorderRecord{full[0], abort, finalized})
	if _, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, records)), validRecorderExpectations(t)); err != nil {
		t.Fatalf("bounded aborted loss evidence rejected: %v", err)
	}
}

func TestVerifyAbortedArtifactsWithReconciledLosses(t *testing.T) {
	blocks := recorderPCAPNGTestBlocks(t, binary.LittleEndian)
	for _, index := range []int{5, 7, 9} {
		binary.LittleEndian.PutUint32(blocks[index][16:20], 1150)
	}
	for _, index := range []int{10, 11, 12} {
		binary.LittleEndian.PutUint32(blocks[index][16:20], 1180)
		binary.LittleEndian.PutUint64(blocks[index][36:44], 1180)
		binary.LittleEndian.PutUint64(blocks[index][48:56], 3)
		binary.LittleEndian.PutUint64(blocks[index][60:68], 1)
		binary.LittleEndian.PutUint64(blocks[index][72:80], 1)
	}
	pcapng := joinRecorderPCAPNGBlocks(blocks)
	full := validRecorderTranscript(t)
	abort := RecorderRecord{
		Schema: RecorderControlSchema, Type: RecorderRecordPhase, RunID: "run-1", InvocationNonce: strings.Repeat("a", 64),
		Ordinal: 2, MonotonicNS: 1100, Phase: RecorderOutcomeAborted,
		Failure: &RecorderFailure{Code: "capture_failed", Message: "synthetic failure"},
	}
	prefix := resealRecorderRecords(t, []RecorderRecord{full[0], abort})
	ledger, err := recorderLedgerBytes(prefix)
	if err != nil {
		t.Fatal(err)
	}
	finalized := full[len(full)-1]
	finalized.Ordinal, finalized.MonotonicNS, finalized.Outcome = 3, 1200, RecorderOutcomeAborted
	finalized.Manifest.Artifacts[0].SHA256, finalized.Manifest.Artifacts[0].SizeBytes = SHA256Hex(pcapng), uint64(len(pcapng))
	finalized.Manifest.Artifacts[1].SHA256, finalized.Manifest.Artifacts[1].SizeBytes = SHA256Hex(ledger), uint64(len(ledger))
	for index := range finalized.Manifest.Interfaces {
		finalized.Manifest.Interfaces[index].Packets = 2
		finalized.Manifest.Interfaces[index].DroppedPackets = 2
		finalized.Manifest.Interfaces[index].TruncatedPackets = uint64(index + 1)
	}
	records := resealRecorderRecords(t, append(prefix, finalized))
	transcript, err := DecodeRecorderTranscript(bytes.NewReader(recorderJSONL(t, records)), validRecorderExpectations(t))
	if err != nil {
		t.Fatal(err)
	}
	if err := VerifyRecorderArtifacts(*transcript, validRecorderExpectations(t), pcapng, ledger); err != nil {
		t.Fatalf("valid aborted capture/loss evidence rejected: %v", err)
	}
}
