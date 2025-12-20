// lib/database-stack.ts
import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";

export class DatabaseStack extends cdk.Stack {
  public readonly waitingRoomTable: dynamodb.Table;
  public readonly chatroomsTable: dynamodb.Table;
  public readonly messagesTable: dynamodb.Table;
  public readonly surveyResponsesTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.waitingRoomTable = new dynamodb.Table(this, "WaitingRoomTable", {
      partitionKey: { name: "id", type: dynamodb.AttributeType.STRING },
      stream: dynamodb.StreamViewType.NEW_IMAGE,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.chatroomsTable = new dynamodb.Table(this, "ChatroomsTable", {
      partitionKey: { name: "id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.messagesTable = new dynamodb.Table(this, "MessagesTable", {
      partitionKey: { name: "chatroomId", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "createdAt", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    this.surveyResponsesTable = new dynamodb.Table(this, "SurveyResponsesTable", {
      partitionKey: { name: "id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Add GSI for filtering by education level, age range, etc.
    this.surveyResponsesTable.addGlobalSecondaryIndex({
      indexName: "education-index",
      partitionKey: { name: "education", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.STRING },
    });

    this.surveyResponsesTable.addGlobalSecondaryIndex({
      indexName: "llmKnowledge-index",
      partitionKey: { name: "llmKnowledge", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.STRING },
    });
  }
}
