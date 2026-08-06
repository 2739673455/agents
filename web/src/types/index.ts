export interface ConversationResponse {
  conversation_id: number;
  title: string;
  update_at: string;
}

export interface ConversationListResponse {
  conversations: ConversationResponse[];
}

export interface Attachment {
  f_path: string;
  preview_url?: string;
}

export interface TextContent {
  type: "text";
  text: string;
}

export interface ImageContent {
  type: "image_url";
  image_url: string;
}

export interface ToolCallPart {
  type: "tool_call";
  tool_call_id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ToolResultPart {
  type: "tool_result";
  tool_call_id: string;
  name: string;
  content: string;
}

export type MessagePart = TextContent | ImageContent | ToolCallPart | ToolResultPart;

export type MessageRole = "user" | "assistant" | "tool" | "system";
export type FinishReason = string;

export interface MessageSchema {
  message_id?: string | null;
  role: MessageRole;
  parts: MessagePart[];
  attachments?: Attachment[] | null;
  finish_reason?: FinishReason | null;
}

export interface MessageListResponse {
  messages: MessageSchema[];
}

export interface UploadAttachmentResponse {
  attachment: Attachment;
}

export interface WebSocketChatRequest {
  message: MessageSchema;
}

export interface WebSocketMessageResponse {
  type: "message";
  message: MessageSchema;
}

export interface WebSocketErrorResponse {
  type: "error";
  content: string;
}
