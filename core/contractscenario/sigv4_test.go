package contractscenario

import (
	"strings"
	"testing"
)

func TestSigV4MatchesPinnedAWSIAMDocumentationVector(t *testing.T) {
	material, err := SignSigV4("wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", SigV4Input{
		Method:   "GET",
		RawPath:  "/",
		RawQuery: "Action=ListUsers&Version=2010-05-08",
		Headers: []Header{
			{Name: "Content-Type", Value: "application/x-www-form-urlencoded; charset=utf-8"},
			{Name: "Host", Value: "iam.amazonaws.com"},
			{Name: "X-Amz-Date", Value: "20150830T123600Z"},
		},
		SignedHeaders: []string{"content-type", "host", "x-amz-date"},
		AmzDate:       "20150830T123600Z",
		Date:          "20150830",
		Region:        "us-east-1",
		Service:       "iam",
	})
	if err != nil {
		t.Fatal(err)
	}
	if material.CredentialScope != "20150830/us-east-1/iam/aws4_request" {
		t.Fatalf("scope = %q", material.CredentialScope)
	}
	if !strings.Contains(material.CanonicalRequest, "\n/\nAction=ListUsers&Version=2010-05-08\n") {
		t.Fatalf("URI and query are not separate canonical fields:\n%s", material.CanonicalRequest)
	}
	const want = "5d672d79c15b13162d9279b0855cfba6789a8edb4c82c400e06b5924a6f2b5d7"
	if material.Signature != want {
		t.Fatalf("signature = %s, want %s\ncanonical:\n%s\nstring-to-sign:\n%s", material.Signature, want, material.CanonicalRequest, material.StringToSign)
	}
}

func TestSigV4PreservesRepeatedEmptyAndLiteralPlusQueryValues(t *testing.T) {
	query, err := canonicalQuery("z=last&a=two&a=&a=one&plus=+")
	if err != nil {
		t.Fatal(err)
	}
	if query != "a=&a=one&a=two&plus=%2B&z=last" {
		t.Fatalf("canonical query = %q", query)
	}
}

func TestSigV4PreservesEscapedSlashAsSegmentData(t *testing.T) {
	path, err := canonicalURI("/models/model%2Fvariant/invoke")
	if err != nil {
		t.Fatal(err)
	}
	if path != "/models/model%2Fvariant/invoke" {
		t.Fatalf("canonical URI = %q", path)
	}
}

func TestSigV4CombinesDuplicateSignedHeadersInWireOrder(t *testing.T) {
	canonical, names, err := canonicalSignedHeaders([]Header{{Name: "X-Test", Value: " a  b "}, {Name: "x-test", Value: "c"}, {Name: "Ignored", Value: "x"}}, []string{"x-test"})
	if err != nil {
		t.Fatal(err)
	}
	if canonical != "x-test:a b,c\n" || names != "x-test" {
		t.Fatalf("headers = %q, names = %q", canonical, names)
	}
}
