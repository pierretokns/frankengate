package configstore

import (
	"errors"
	"fmt"
	"strings"
)

var ErrNotFound = errors.New("not found")
var ErrAlreadyExists = errors.New("already exists")
var ErrMCPAccessDenied = errors.New("virtual key no longer grants access to MCP client")
var ErrMCPConcurrentUpdate = errors.New("MCP client changed concurrently")

// ErrUnresolvedKeys is returned when one or more keys could not be resolved
type ErrUnresolvedKeys struct {
	Identifiers []string
}

func (e *ErrUnresolvedKeys) Error() string {
	return fmt.Sprintf("could not resolve keys: %s", strings.Join(e.Identifiers, ", "))
}
