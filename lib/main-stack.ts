// lib/main-stack.ts
import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import { DatabaseStack } from "./database-stack";
import { SecretsStack } from "./secrets-stack";
import { ApiLambdasStack } from "./api-lambdas-stack";

export class MainStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create the database stack
    const databaseStack = new DatabaseStack(this, "DatabaseStack");

    // Create the secrets stack
    const secretsStack = new SecretsStack(this, "SecretsStack");

    // Create the combined API and Lambdas stack
    const apiLambdasStack = new ApiLambdasStack(this, "ApiLambdasStack", {
      waitingRoomTable: databaseStack.waitingRoomTable,
      chatroomsTable: databaseStack.chatroomsTable,
      messagesTable: databaseStack.messagesTable,
      surveyResponsesTable: databaseStack.surveyResponsesTable,
      openAiApiKeySecret: secretsStack.openAiApiKeySecret,
    });

    // Add explicit dependencies
    apiLambdasStack.addDependency(databaseStack);
    apiLambdasStack.addDependency(secretsStack);
  }
}
