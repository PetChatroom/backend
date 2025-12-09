// lib/api-lambdas-stack.ts
import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as path from "path";
import * as lambda from "aws-cdk-lib/aws-lambda";
import { RetentionDays } from "aws-cdk-lib/aws-logs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import * as eventsources from "aws-cdk-lib/aws-lambda-event-sources";
import * as appsync from "aws-cdk-lib/aws-appsync";
import * as ssm from "aws-cdk-lib/aws-ssm";
import * as iam from "aws-cdk-lib/aws-iam";

interface ApiLambdasStackProps extends cdk.StackProps {
  waitingRoomTable: dynamodb.Table;
  chatroomsTable: dynamodb.Table;
  messagesTable: dynamodb.Table;
  openAiApiKeySecret: secretsmanager.ISecret;
}

export class ApiLambdasStack extends cdk.Stack {
  public readonly api: appsync.GraphqlApi;
  public readonly aiResponseLambda: lambda.Function;
  public readonly messageHandlerLambda: lambda.Function;
  public readonly joinWaitingRoomLambda: lambda.Function;
  public readonly matchmakingLambda: lambda.Function;
  public readonly createMatchLambda: lambda.Function;
  public readonly getWaitingStatusLambda: lambda.Function;
  public readonly leaveWaitingRoomLambda: lambda.Function;

  constructor(scope: Construct, id: string, props: ApiLambdasStackProps) {
    super(scope, id, props);

    const envSuffix = this.node.tryGetContext("env") || "dev";

    // --- API Resources ---
    this.api = new appsync.GraphqlApi(this, "TuringGameApi", {
      name: "turing-game-api",
      definition: appsync.Definition.fromFile("lib/schema.graphql"),
      authorizationConfig: {
        defaultAuthorization: {
          authorizationType: appsync.AuthorizationType.API_KEY,
          apiKeyConfig: {
            expires: cdk.Expiration.after(cdk.Duration.days(365)),
          },
        },
      },
      xrayEnabled: false,
    });

    const aiPromptParameterName = "/turing-game/prompts/ai-personality";

    // This does NOT create a resource. It creates a reference in your CDK app
    // to the parameter that you created manually in the console.
    const aiPromptParameter = ssm.StringParameter.fromStringParameterName(
      this,
      "AiPromptParameterLookup",
      aiPromptParameterName
    );

    // --- Lambda Functions ---
    // AI Response Lambda
    this.aiResponseLambda = new lambda.Function(this, "AiResponseHandler", {
      runtime: lambda.Runtime.PYTHON_3_9,
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../lambda/ai_response/package")
      ),
      handler: "ai_response.handler",
      environment: {
        MESSAGES_TABLE: props.messagesTable.tableName,
        CHATROOMS_TABLE: props.chatroomsTable.tableName,
        OPENAI_API_KEY_SECRET_NAME: props.openAiApiKeySecret.secretName,
        APPSYNC_URL: this.api.graphqlUrl,
        APPSYNC_API_KEY: this.api.apiKey || "no-key-generated",
        AI_PROMPT_PARAMETER: aiPromptParameterName,
      },
      functionName: `airesponse-${envSuffix}`,
      logRetention: RetentionDays.ONE_MONTH,
      timeout: cdk.Duration.seconds(30),
    });

    // Message Handler Lambda
    this.messageHandlerLambda = new lambda.Function(this, "MessageHandler", {
      runtime: lambda.Runtime.PYTHON_3_9,
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../lambda/message_handler/package")
      ),
      handler: "message_handler.handler",
      environment: {
        MESSAGES_TABLE: props.messagesTable.tableName,
        AI_RESPONSE_LAMBDA_NAME: this.aiResponseLambda.functionName,
      },
      functionName: `messagehandler-${envSuffix}`,
      logRetention: RetentionDays.ONE_MONTH,
    });

    // Join Waiting Room Lambda
    this.joinWaitingRoomLambda = new lambda.Function(
      this,
      "JoinWaitingRoomHandler",
      {
        runtime: lambda.Runtime.PYTHON_3_9,
        code: lambda.Code.fromAsset(
          path.join(__dirname, "../lambda/join_waiting_room/package")
        ),
        handler: "join_waiting_room.handler",
        environment: {
          WAITING_ROOM_TABLE: props.waitingRoomTable.tableName,
        },
        functionName: `joinwaitingroom-${envSuffix}`,
        logRetention: RetentionDays.ONE_MONTH,
      }
    );

    // Create Match Lambda
    this.createMatchLambda = new lambda.Function(this, "CreateMatchHandler", {
      runtime: lambda.Runtime.PYTHON_3_9,
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../lambda/create_match/package")
      ),
      handler: "create_match.handler",
      functionName: `creatematch-${envSuffix}`,
      logRetention: RetentionDays.ONE_MONTH,
    });

    // Matchmaking Lambda
    this.matchmakingLambda = new lambda.Function(this, "MatchmakingHandler", {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: "matchmaking.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../lambda/matchmaking/package")
      ),
      environment: {
        WAITING_ROOM_TABLE: props.waitingRoomTable.tableName,
        CHATROOMS_TABLE: props.chatroomsTable.tableName,
        APPSYNC_URL: this.api.graphqlUrl,
        APPSYNC_API_KEY: this.api.apiKey || "no-key-generated",
      },
      functionName: `matchmaking-${envSuffix}`,
      logRetention: RetentionDays.ONE_MONTH,
      timeout: cdk.Duration.seconds(30),
    });

    // Get Waiting Status Lambda
    this.getWaitingStatusLambda = new lambda.Function(
      this,
      "GetWaitingStatusHandler",
      {
        runtime: lambda.Runtime.PYTHON_3_9,
        code: lambda.Code.fromAsset(
          path.join(__dirname, "../lambda/get_waiting_status/package")
        ),
        handler: "get_waiting_status.handler",
        environment: {
          WAITING_ROOM_TABLE: props.waitingRoomTable.tableName,
          CHATROOMS_TABLE: props.chatroomsTable.tableName,
        },
        functionName: `getwaitingstatus-${envSuffix}`,
        logRetention: RetentionDays.ONE_MONTH,
      }
    );

    // Leave Waiting Room Lambda
    this.leaveWaitingRoomLambda = new lambda.Function(
      this,
      "LeaveWaitingRoomHandler",
      {
        runtime: lambda.Runtime.PYTHON_3_9,
        code: lambda.Code.fromAsset(
          path.join(__dirname, "../lambda/leave_waiting_room/package")
        ),
        handler: "leave_waiting_room.handler",
        environment: {
          WAITING_ROOM_TABLE: props.waitingRoomTable.tableName,
        },
        functionName: `leavewaitingroom-${envSuffix}`,
        logRetention: RetentionDays.ONE_MONTH,
      }
    );

    // --- CREATE DATA SOURCES AND RESOLVERS ---
    const messageHandlerDataSource = this.api.addLambdaDataSource(
      "MessageHandlerDataSource",
      this.messageHandlerLambda
    );
    messageHandlerDataSource.createResolver("SendMessageResolver", {
      typeName: "Mutation",
      fieldName: "sendMessage",
    });

    const joinWaitingRoomDataSource = this.api.addLambdaDataSource(
      "JoinWaitingRoomDataSource",
      this.joinWaitingRoomLambda
    );
    joinWaitingRoomDataSource.createResolver("JoinWaitingRoomResolver", {
      typeName: "Mutation",
      fieldName: "joinWaitingRoom",
    });

    const leaveWaitingRoomDataSource = this.api.addLambdaDataSource(
      "LeaveWaitingRoomDataSource",
      this.leaveWaitingRoomLambda
    );
    leaveWaitingRoomDataSource.createResolver("LeaveWaitingRoomResolver", {
      typeName: "Mutation",
      fieldName: "leaveWaitingRoom",
    });

    const createMatchDataSource = this.api.addLambdaDataSource(
      "CreateMatchDataSource",
      this.createMatchLambda
    );
    createMatchDataSource.createResolver("CreateMatchResolver", {
      typeName: "Mutation",
      fieldName: "createMatch",
    });

    const getWaitingStatusDataSource = this.api.addLambdaDataSource(
      "GetWaitingStatusDataSource",
      this.getWaitingStatusLambda
    );
    getWaitingStatusDataSource.createResolver("GetWaitingStatusResolver", {
      typeName: "Query",
      fieldName: "getWaitingStatus",
    });

    const messagesTableDataSource = this.api.addDynamoDbDataSource(
      "MessagesTableDataSource",
      props.messagesTable
    );
    messagesTableDataSource.createResolver("QueryGetMessagesResolver", {
      typeName: "Query",
      fieldName: "getMessages",
      requestMappingTemplate: appsync.MappingTemplate.dynamoDbQuery(
        appsync.KeyCondition.eq("chatroomId", "chatroomId")
      ),
      responseMappingTemplate: appsync.MappingTemplate.dynamoDbResultList(),
    });

    // --- TRIGGERS ---
    props.waitingRoomTable.grantStreamRead(this.matchmakingLambda);
    this.matchmakingLambda.addEventSource(
      new eventsources.DynamoEventSource(props.waitingRoomTable, {
        startingPosition: lambda.StartingPosition.LATEST,
        batchSize: 1,
        bisectBatchOnError: true,
      })
    );

    // --- GRANT PERMISSIONS ---
    props.openAiApiKeySecret.grantRead(this.aiResponseLambda);
    props.chatroomsTable.grantReadData(this.aiResponseLambda);
    props.messagesTable.grantReadWriteData(this.aiResponseLambda);
    props.messagesTable.grantReadWriteData(this.messageHandlerLambda);

    // Grant invoke permission
    this.aiResponseLambda.grantInvoke(this.messageHandlerLambda);
    aiPromptParameter.grantRead(this.aiResponseLambda);

    props.waitingRoomTable.grantReadWriteData(this.matchmakingLambda);
    props.chatroomsTable.grantReadWriteData(this.matchmakingLambda);
    props.waitingRoomTable.grantReadWriteData(this.joinWaitingRoomLambda);
    props.waitingRoomTable.grantReadData(this.getWaitingStatusLambda);
    props.chatroomsTable.grantReadData(this.getWaitingStatusLambda);
    props.waitingRoomTable.grantReadWriteData(this.leaveWaitingRoomLambda);

    // Grant AppSync mutation permissions
    this.matchmakingLambda.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["appsync:GraphQL"],
        resources: [this.api.arn],
      })
    );

    // Grant additional permissions needed by AppSync
    props.messagesTable.grantReadData(messagesTableDataSource);

    // --- STACK OUTPUTS AND PARAMETERS ---
    new ssm.StringParameter(this, "ApiUrlParameter", {
      parameterName: "/turing-game/graphql-api-url",
      stringValue: this.api.graphqlUrl,
    });
    new ssm.StringParameter(this, "ApiKeyParameter", {
      parameterName: "/turing-game/graphql-api-key",
      stringValue: this.api.apiKey || "no-key-generated",
    });

    new cdk.CfnOutput(this, "GraphQLAPIURL", { value: this.api.graphqlUrl });
    new cdk.CfnOutput(this, "GraphQLAPIKey", {
      value: this.api.apiKey || "No API Key",
    });
    new cdk.CfnOutput(this, "AppSyncApiId", { value: this.api.apiId });
  }
}
