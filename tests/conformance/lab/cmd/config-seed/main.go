package main

import (
	"context"
	"fmt"
	"os"
	"time"

	bifrost "github.com/maximhq/bifrost/core"
	"github.com/maximhq/bifrost/core/schemas"
	"github.com/maximhq/bifrost/framework/configstore"
)

const (
	seedRevision    = "sealed-lab-c9-gpt55-v1"
	providerKeyID   = "00000000-0000-4000-8000-000000000055"
	providerKeyName = "sealed-mantle-gpt55"
	providerAPIKey  = "synthetic-mantle-contract"
	aliasName       = "gpt-5.5"
	upstreamModel   = "openai.gpt-5.5"
)

func main() {
	if err := seed(context.Background()); err != nil {
		fmt.Fprintln(os.Stderr, "config-seed:", err)
		os.Exit(1)
	}
}

func seed(ctx context.Context) error {
	caPEM, err := os.ReadFile("/lab-tls/ca.pem")
	if err != nil || len(caPEM) == 0 {
		return fmt.Errorf("read sealed lab CA: %w", err)
	}
	store, err := configstore.NewConfigStore(ctx, &configstore.Config{
		Enabled: true,
		Type:    configstore.ConfigStoreTypePostgres,
		Config: &configstore.PostgresConfig{
			Host: schemas.NewSecretVar("postgres"), Port: schemas.NewSecretVar("5432"),
			User: schemas.NewSecretVar("bifrost"), Password: schemas.NewSecretVar("sealed-lab-only"),
			DBName: schemas.NewSecretVar("bifrost"), SSLMode: schemas.NewSecretVar("disable"),
			MaxIdleConns: 2, MaxOpenConns: 4, ConnMaxLifetime: "1m",
		},
	}, bifrost.NewNoOpLogger())
	if err != nil {
		return err
	}
	defer store.Close(ctx)

	enabled := true
	family := schemas.ModelFamilyOpenAI
	modelName := upstreamModel
	config := configstore.ProviderConfig{
		NetworkConfig: &schemas.NetworkConfig{
			DefaultRequestTimeoutInSeconds: 30,
			MaxConnsPerHost:                32,
			AllowPrivateNetwork:            true,
			CACertPEM:                      schemas.NewSecretVar(string(caPEM)),
		},
		SendBackRawRequest:      true,
		SendBackRawResponse:     true,
		StoreRawRequestResponse: true,
		Keys: []schemas.Key{{
			ID: providerKeyID, Name: providerKeyName, Value: *schemas.NewSecretVar(providerAPIKey),
			Models: schemas.WhiteList{aliasName}, Weight: 1, Enabled: &enabled,
			Aliases: schemas.KeyAliases{aliasName: {
				ModelID: upstreamModel, ModelName: &modelName, ModelFamily: &family,
			}},
			BedrockMantleKeyConfig: &schemas.BedrockMantleKeyConfig{
				Region: schemas.NewSecretVar("us-east-1"),
			},
		}},
		ConfigHash:  "sealed-lab-c9-gpt55-v1",
		Status:      "active",
		Description: "sealed deterministic GPT-5.5 C9 slice",
	}
	if err := store.UpdateProvidersConfig(ctx, map[schemas.ModelProvider]configstore.ProviderConfig{
		schemas.BedrockMantle: config,
	}); err != nil {
		return fmt.Errorf("seed PostgreSQL provider authority: %w", err)
	}
	deadline, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()
	providers, err := store.GetProvidersConfig(deadline)
	if err != nil {
		return fmt.Errorf("read seeded provider authority: %w", err)
	}
	seeded, ok := providers[schemas.BedrockMantle]
	if !ok || len(seeded.Keys) != 1 || seeded.Keys[0].ID != providerKeyID || seeded.Keys[0].Aliases[aliasName].ModelID != upstreamModel || seeded.NetworkConfig == nil || seeded.NetworkConfig.InsecureSkipVerify || seeded.NetworkConfig.CACertPEM == nil || seeded.NetworkConfig.CACertPEM.GetValue() == "" {
		return fmt.Errorf("seeded provider authority failed closed verification")
	}
	fmt.Printf("{\"schema\":\"sealed-lab-config-seed/v1\",\"revision\":%q,\"provider\":\"bedrock_mantle\",\"alias\":\"gpt-5.5\",\"model\":\"openai.gpt-5.5\",\"tls\":\"private-ca-verified\"}\n", seedRevision)
	return nil
}
