// lib/secrets-stack.ts
import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";

export class SecretsStack extends cdk.Stack {
  public readonly openAiApiKeySecret: secretsmanager.ISecret;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create the secret instead of importing it
    this.openAiApiKeySecret = new secretsmanager.Secret(
      this,
      "OpenAiApiKeySecret",
      {
        secretName: "Turing-Open-AI-API-Key",
        description: "OpenAI API Key for Turing Game",
      }
    );
  }
}
