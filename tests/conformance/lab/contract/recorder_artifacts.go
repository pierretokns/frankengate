package contract

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"math"
	"strconv"
)

const (
	pcapngSectionHeaderBlock   = uint32(0x0a0d0d0a)
	pcapngInterfaceDescription = uint32(0x00000001)
	pcapngEnhancedPacket       = uint32(0x00000006)
	pcapngInterfaceStatistics  = uint32(0x00000005)
	pcapngByteOrderMagic       = uint32(0x1a2b3c4d)
	pcapngEthernetLinkType     = uint16(1)
	pcapngIfNameOption         = uint16(2)
	pcapngIfDescriptionOption  = uint16(3)
	pcapngISBStartTimeOption   = uint16(2)
	pcapngISBEndTimeOption     = uint16(3)
	pcapngISBIfRecvOption      = uint16(4)
	pcapngISBIfDropOption      = uint16(5)
	pcapngISBOSDropOption      = uint16(7)
	maxRecorderPacketBytes     = 1 << 20

	RecorderCalibrationStart = "start"
	RecorderCalibrationEnd   = "end"
)

var recorderCalibrationDestination = [6]byte{0x02, 0x46, 0x47, 0x00, 0x00, 0x01}
var recorderCalibrationSource = [6]byte{0x02, 0x46, 0x47, 0x00, 0x00, 0x02}

// RecorderCalibrationFrame returns the exact 60-byte synthetic Ethernet frame
// used to prove per-interface capture coverage. It uses fixed locally
// administered MACs, experimental Ethertype 0x88b5, and a printable-ASCII
// 46-byte payload containing a nonce/role/marker-derived digest token.
func RecorderCalibrationFrame(nonce, role, marker string) ([]byte, error) {
	if !invocationNonce.MatchString(nonce) || (role != "client_net" && role != "control_net" && role != "data_net") || (marker != RecorderCalibrationStart && marker != RecorderCalibrationEnd) {
		return nil, fmt.Errorf("invalid recorder calibration identity")
	}
	digest := sha256.Sum256([]byte(nonce + "\x00" + role + "\x00" + marker))
	payload := "fgcal1|" + role + "|" + marker + "|" + hex.EncodeToString(digest[:10])
	if len(payload) > 46 {
		return nil, fmt.Errorf("recorder calibration payload exceeds Ethernet minimum payload")
	}
	frame := make([]byte, 60)
	copy(frame[0:6], recorderCalibrationDestination[:])
	copy(frame[6:12], recorderCalibrationSource[:])
	frame[12], frame[13] = 0x88, 0xb5
	copy(frame[14:], payload)
	for index := 14 + len(payload); index < len(frame); index++ {
		frame[index] = ' '
	}
	return frame, nil
}

// VerifyRecorderArtifacts verifies already extracted, trusted in-memory bytes.
// Extraction ownership and no-symlink enforcement belong to the runner. This
// verifier proves only internal contract consistency; it does not prove that a
// capture occurred or that an upstream provider did not bill a request.
//
// V1 counter semantics are intentionally exact: manifest packets equal emitted
// EPBs; ISB ifrecv equals EPBs plus osdrop; manifest dropped_packets equals
// ifdrop plus osdrop. Every accepted EPB has caplen == origlen; an aborted
// transcript may separately preserve its bounded truncated_packets diagnostic
// for frames it refused to emit. A complete transcript requires that diagnostic
// and both ISB drop counters to be zero.
func VerifyRecorderArtifacts(transcript RecorderTranscript, expected RecorderExpectations, pcapng, ledger []byte) error {
	if err := transcript.Validate(expected); err != nil {
		return fmt.Errorf("validate recorder transcript before artifacts: %w", err)
	}
	finalized := transcript.Records[len(transcript.Records)-1]
	manifest := finalized.Manifest
	if manifest == nil {
		return fmt.Errorf("recorder transcript has no artifact manifest")
	}
	if err := verifyRecorderArtifactBytes(manifest.Artifacts[0], pcapng); err != nil {
		return fmt.Errorf("pcapng artifact: %w", err)
	}
	if err := verifyRecorderArtifactBytes(manifest.Artifacts[1], ledger); err != nil {
		return fmt.Errorf("ledger artifact: %w", err)
	}
	wantLedger, err := recorderLedgerBytes(transcript.Records[:len(transcript.Records)-1])
	if err != nil {
		return err
	}
	if !bytes.Equal(ledger, wantLedger) {
		return fmt.Errorf("ledger is not canonical JSONL for the sealed pre-FINALIZED records")
	}
	window, err := recorderLifecycleWindow(transcript)
	if err != nil {
		return err
	}
	packetCounts, interfaceStats, err := parseRecorderPCAPNG(pcapng, expected, window)
	if err != nil {
		return err
	}
	for index, count := range packetCounts {
		if count != manifest.Interfaces[index].Packets {
			return fmt.Errorf("pcapng interface[%d] packet count %d does not match manifest %d", index, count, manifest.Interfaces[index].Packets)
		}
		stats := interfaceStats[index]
		if stats.OSDrop > math.MaxUint64-count || stats.IfRecv != count+stats.OSDrop {
			return fmt.Errorf("pcapng interface[%d] ifrecv does not reconcile with EPBs and osdrop", index)
		}
		if stats.IfDrop > math.MaxUint64-stats.OSDrop || manifest.Interfaces[index].DroppedPackets != stats.IfDrop+stats.OSDrop {
			return fmt.Errorf("pcapng interface[%d] loss counters do not reconcile with manifest", index)
		}
	}
	return nil
}

type recorderCaptureWindow struct {
	ReadyNS          uint64
	EndCalibrationNS uint64
	EndCoverageNS    uint64
	FinalizedNS      uint64
}

func recorderLifecycleWindow(transcript RecorderTranscript) (recorderCaptureWindow, error) {
	window := recorderCaptureWindow{ReadyNS: transcript.Records[0].MonotonicNS, FinalizedNS: transcript.Records[len(transcript.Records)-1].MonotonicNS}
	for _, record := range transcript.Records[1 : len(transcript.Records)-1] {
		switch record.Phase {
		case RecorderPhaseTeardownStarting:
			window.EndCalibrationNS = record.MonotonicNS
		case RecorderPhaseTopologyRemoved:
			window.EndCoverageNS = record.MonotonicNS
		case RecorderOutcomeAborted:
			window.EndCalibrationNS = record.MonotonicNS
			window.EndCoverageNS = record.MonotonicNS
		}
	}
	if window.ReadyNS == 0 || window.EndCalibrationNS == 0 || window.EndCoverageNS == 0 || window.EndCoverageNS > window.FinalizedNS {
		return window, fmt.Errorf("recorder transcript lacks a valid capture lifecycle window")
	}
	return window, nil
}

func verifyRecorderArtifactBytes(artifact RecorderArtifact, data []byte) error {
	maximum := uint64(0)
	switch artifact.Kind {
	case "pcapng":
		maximum = maxRecorderPCAPNGBytes
	case "ledger":
		maximum = maxRecorderLedgerBytes
	default:
		return fmt.Errorf("unsupported artifact kind %q", artifact.Kind)
	}
	if len(data) == 0 || uint64(len(data)) > maximum {
		return fmt.Errorf("artifact bytes violate bounded nonempty contract")
	}
	if uint64(len(data)) != artifact.SizeBytes {
		return fmt.Errorf("artifact size does not match manifest")
	}
	if SHA256Hex(data) != artifact.SHA256 {
		return fmt.Errorf("artifact hash does not match manifest")
	}
	return nil
}

// recorderLedgerBytes returns canonical JSONL for every sealed control record
// preceding FINALIZED. Excluding FINALIZED prevents the ledger digest in its
// manifest from becoming circular. Each line uses RecorderRecord's declared
// field order, compact UTF-8 JSON, printable-ASCII strings, HTML escaping off,
// and exactly one LF delimiter.
func recorderLedgerBytes(records []RecorderRecord) ([]byte, error) {
	if len(records) == 0 || len(records) >= maxRecorderRecords {
		return nil, fmt.Errorf("invalid recorder ledger record count")
	}
	var output bytes.Buffer
	for index, record := range records {
		if record.Type == RecorderRecordFinalized || !sha256Value.MatchString(record.RecordSHA256) {
			return nil, fmt.Errorf("ledger record[%d] is unsealed or FINALIZED", index)
		}
		if err := validateRecorderPrintableASCII(record); err != nil {
			return nil, err
		}
		line, err := compactRecorderJSON(record)
		if err != nil {
			return nil, err
		}
		if output.Len()+len(line)+1 > maxRecorderTranscriptBytes {
			return nil, fmt.Errorf("recorder ledger exceeds bounded contract")
		}
		output.Write(line)
		output.WriteByte('\n')
	}
	return output.Bytes(), nil
}

type recorderInterfaceStats struct {
	StartNS uint64
	EndNS   uint64
	IfRecv  uint64
	IfDrop  uint64
	OSDrop  uint64
}

func parseRecorderPCAPNG(data []byte, expected RecorderExpectations, window recorderCaptureWindow) ([3]uint64, [3]recorderInterfaceStats, error) {
	var counts [3]uint64
	var stats [3]recorderInterfaceStats
	if len(data) < 28 || len(data) > maxRecorderPCAPNGBytes {
		return counts, stats, fmt.Errorf("pcapng violates bounded section size")
	}
	if binary.LittleEndian.Uint32(data[:4]) != pcapngSectionHeaderBlock {
		return counts, stats, fmt.Errorf("pcapng does not begin with a section header")
	}
	var order binary.ByteOrder
	switch {
	case binary.LittleEndian.Uint32(data[8:12]) == pcapngByteOrderMagic:
		order = binary.LittleEndian
	case binary.BigEndian.Uint32(data[8:12]) == pcapngByteOrderMagic:
		order = binary.BigEndian
	default:
		return counts, stats, fmt.Errorf("pcapng has invalid byte-order magic")
	}
	offset := 0
	block, next, err := recorderPCAPNGBlock(data, offset, order)
	if err != nil {
		return counts, stats, err
	}
	if order.Uint32(block[:4]) != pcapngSectionHeaderBlock || len(block) != 28 || order.Uint16(block[12:14]) != 1 || order.Uint16(block[14:16]) != 0 || order.Uint64(block[16:24]) != math.MaxUint64 {
		return counts, stats, fmt.Errorf("pcapng section header is not the strict v1 unknown-length form")
	}
	offset = next

	snapLengths := [3]uint32{}
	for index := 0; index < len(expected.Bridges); index++ {
		block, next, err = recorderPCAPNGBlock(data, offset, order)
		if err != nil {
			return counts, stats, err
		}
		if order.Uint32(block[:4]) != pcapngInterfaceDescription || len(block) < 28 || order.Uint16(block[8:10]) != pcapngEthernetLinkType || order.Uint16(block[10:12]) != 0 {
			return counts, stats, fmt.Errorf("pcapng interface[%d] is not an Ethernet IDB", index)
		}
		snapLengths[index] = order.Uint32(block[12:16])
		if snapLengths[index] == 0 || snapLengths[index] > maxRecorderPacketBytes {
			return counts, stats, fmt.Errorf("pcapng interface[%d] has invalid snaplen", index)
		}
		name, description, err := recorderPCAPNGInterfaceOptions(block[16:len(block)-4], order)
		if err != nil {
			return counts, stats, fmt.Errorf("pcapng interface[%d]: %w", index, err)
		}
		bridge := expected.Bridges[index]
		if name != bridge.Name || description != "linux-ifindex="+strconv.FormatUint(uint64(bridge.IfIndex), 10) {
			return counts, stats, fmt.Errorf("pcapng interface[%d] name or Linux ifindex does not match trusted READY order", index)
		}
		offset = next
	}

	timestamps := [3][]uint64{}
	packets := [3][][]byte{}
	for offset < len(data) {
		block, next, err = recorderPCAPNGBlock(data, offset, order)
		if err != nil {
			return counts, stats, err
		}
		if order.Uint32(block[:4]) == pcapngInterfaceStatistics {
			break
		}
		if order.Uint32(block[:4]) != pcapngEnhancedPacket || len(block) < 32 {
			return counts, stats, fmt.Errorf("pcapng contains unsupported block type or malformed EPB")
		}
		interfaceID := order.Uint32(block[8:12])
		if interfaceID >= uint32(len(expected.Bridges)) {
			return counts, stats, fmt.Errorf("pcapng EPB references unknown interface %d", interfaceID)
		}
		timestamp := uint64(order.Uint32(block[12:16]))<<32 | uint64(order.Uint32(block[16:20]))
		capturedLength := order.Uint32(block[20:24])
		originalLength := order.Uint32(block[24:28])
		if timestamp == 0 || timestamp > math.MaxInt64 || capturedLength < 60 || capturedLength != originalLength || capturedLength > snapLengths[interfaceID] || capturedLength > maxRecorderPacketBytes {
			return counts, stats, fmt.Errorf("pcapng EPB has zero time, a sub-Ethernet frame, truncation, or oversize")
		}
		paddedLength := (uint64(capturedLength) + 3) &^ uint64(3)
		if paddedLength > math.MaxInt || uint64(len(block)) != 32+paddedLength {
			return counts, stats, fmt.Errorf("pcapng EPB has options or inconsistent packet length")
		}
		paddingStart := 28 + int(capturedLength)
		paddingEnd := 28 + int(paddedLength)
		for _, value := range block[paddingStart:paddingEnd] {
			if value != 0 {
				return counts, stats, fmt.Errorf("pcapng EPB has nonzero packet padding")
			}
		}
		if counts[interfaceID] == maxRecorderCounter {
			return counts, stats, fmt.Errorf("pcapng packet counter exceeds bounded contract")
		}
		if prior := timestamps[interfaceID]; len(prior) > 0 && timestamp < prior[len(prior)-1] {
			return counts, stats, fmt.Errorf("pcapng interface[%d] timestamps regress", interfaceID)
		}
		timestamps[interfaceID] = append(timestamps[interfaceID], timestamp)
		packets[interfaceID] = append(packets[interfaceID], append([]byte(nil), block[28:28+int(capturedLength)]...))
		counts[interfaceID]++
		offset = next
	}

	for index := 0; index < len(expected.Bridges); index++ {
		block, next, err = recorderPCAPNGBlock(data, offset, order)
		if err != nil {
			return counts, stats, err
		}
		if order.Uint32(block[:4]) != pcapngInterfaceStatistics || len(block) < 24 || order.Uint32(block[8:12]) != uint32(index) {
			return counts, stats, fmt.Errorf("pcapng ISB[%d] is missing, duplicated, or out of order", index)
		}
		blockTimestamp := uint64(order.Uint32(block[12:16]))<<32 | uint64(order.Uint32(block[16:20]))
		stats[index], err = recorderPCAPNGStatisticsOptions(block[20:len(block)-4], order)
		if err != nil {
			return counts, stats, fmt.Errorf("pcapng ISB[%d]: %w", index, err)
		}
		if blockTimestamp == 0 || blockTimestamp != stats[index].EndNS {
			return counts, stats, fmt.Errorf("pcapng ISB[%d] header timestamp does not equal endtime", index)
		}
		offset = next
	}
	if offset != len(data) {
		return counts, stats, fmt.Errorf("pcapng has trailing, duplicate, or unsupported blocks")
	}

	for index, bridge := range expected.Bridges {
		if len(timestamps[index]) == 0 || stats[index].StartNS == 0 || stats[index].StartNS > stats[index].EndNS || stats[index].EndNS > window.FinalizedNS {
			return counts, stats, fmt.Errorf("pcapng interface[%d] has invalid ISB capture window", index)
		}
		startFrame, err := RecorderCalibrationFrame(expected.InvocationNonce, bridge.Role, RecorderCalibrationStart)
		if err != nil {
			return counts, stats, err
		}
		endFrame, err := RecorderCalibrationFrame(expected.InvocationNonce, bridge.Role, RecorderCalibrationEnd)
		if err != nil {
			return counts, stats, err
		}
		startCount, endCount := 0, 0
		startTimestamp, endTimestamp := uint64(0), uint64(0)
		for packetIndex, packet := range packets[index] {
			if bytes.Equal(packet, startFrame) {
				startCount++
				startTimestamp = timestamps[index][packetIndex]
			}
			if bytes.Equal(packet, endFrame) {
				endCount++
				endTimestamp = timestamps[index][packetIndex]
			}
		}
		if startCount != 1 || endCount != 1 || !bytes.Equal(packets[index][0], startFrame) || !bytes.Equal(packets[index][len(packets[index])-1], endFrame) {
			return counts, stats, fmt.Errorf("pcapng interface[%d] lacks unique boundary calibration frames", index)
		}
		if stats[index].StartNS > startTimestamp || startTimestamp > window.ReadyNS || endTimestamp < window.EndCalibrationNS || endTimestamp > stats[index].EndNS || stats[index].EndNS < window.EndCoverageNS {
			return counts, stats, fmt.Errorf("pcapng interface[%d] calibration or ISB times do not bracket lifecycle", index)
		}
	}
	return counts, stats, nil
}

func recorderPCAPNGBlock(data []byte, offset int, order binary.ByteOrder) ([]byte, int, error) {
	if offset < 0 || len(data)-offset < 12 {
		return nil, offset, fmt.Errorf("pcapng contains a truncated block header")
	}
	totalLength := order.Uint32(data[offset+4 : offset+8])
	if totalLength < 12 || totalLength%4 != 0 || uint64(totalLength) > uint64(len(data)-offset) {
		return nil, offset, fmt.Errorf("pcapng block has invalid bounded total length")
	}
	end := offset + int(totalLength)
	if order.Uint32(data[end-4:end]) != totalLength {
		return nil, offset, fmt.Errorf("pcapng block length trailer mismatch")
	}
	return data[offset:end], end, nil
}

func recorderPCAPNGInterfaceOptions(options []byte, order binary.ByteOrder) (string, string, error) {
	values, err := recorderPCAPNGExactOptions(options, order, []uint16{pcapngIfNameOption, pcapngIfDescriptionOption})
	if err != nil {
		return "", "", err
	}
	name, description := string(values[0]), string(values[1])
	if name == "" || description == "" {
		return "", "", fmt.Errorf("IDB omits if_name or if_description")
	}
	if err := validateASCIIStrings(name, description); err != nil {
		return "", "", err
	}
	return name, description, nil
}

func recorderPCAPNGStatisticsOptions(options []byte, order binary.ByteOrder) (recorderInterfaceStats, error) {
	var stats recorderInterfaceStats
	values, err := recorderPCAPNGExactOptions(options, order, []uint16{pcapngISBStartTimeOption, pcapngISBEndTimeOption, pcapngISBIfRecvOption, pcapngISBIfDropOption, pcapngISBOSDropOption})
	if err != nil {
		return stats, err
	}
	for index, value := range values {
		if len(value) != 8 {
			return stats, fmt.Errorf("ISB option[%d] is not an 8-byte counter", index)
		}
	}
	stats.StartNS = order.Uint64(values[0])
	stats.EndNS = order.Uint64(values[1])
	stats.IfRecv = order.Uint64(values[2])
	stats.IfDrop = order.Uint64(values[3])
	stats.OSDrop = order.Uint64(values[4])
	if stats.StartNS == 0 || stats.StartNS > math.MaxInt64 || stats.EndNS == 0 || stats.EndNS > math.MaxInt64 || stats.IfRecv > maxRecorderCounter || stats.IfDrop > maxRecorderCounter || stats.OSDrop > maxRecorderCounter {
		return recorderInterfaceStats{}, fmt.Errorf("ISB timestamps or counters exceed bounded contract")
	}
	return stats, nil
}

func recorderPCAPNGExactOptions(options []byte, order binary.ByteOrder, wantCodes []uint16) ([][]byte, error) {
	values := make([][]byte, 0, len(wantCodes))
	offset := 0
	for _, wantCode := range wantCodes {
		if len(options)-offset < 4 {
			return nil, fmt.Errorf("missing required option %d", wantCode)
		}
		code := order.Uint16(options[offset : offset+2])
		length := int(order.Uint16(options[offset+2 : offset+4]))
		offset += 4
		paddedLength := (length + 3) &^ 3
		if code != wantCode || length == 0 || paddedLength > len(options)-offset {
			return nil, fmt.Errorf("unknown, duplicate, missing, or malformed option; got %d want %d", code, wantCode)
		}
		value := options[offset : offset+length]
		for _, padding := range options[offset+length : offset+paddedLength] {
			if padding != 0 {
				return nil, fmt.Errorf("option %d has nonzero padding", code)
			}
		}
		values = append(values, value)
		offset += paddedLength
	}
	if len(options)-offset != 4 || order.Uint16(options[offset:offset+2]) != 0 || order.Uint16(options[offset+2:offset+4]) != 0 {
		return nil, fmt.Errorf("options omit their exact terminal end marker or contain extras")
	}
	return values, nil
}
