# Transcript Question Answering Feature

## Overview

I have successfully implemented a new feature that allows users to ask questions about transcription files using Claude Sonnet 4. When a user replies to a transcript file with a question, the bot will analyze the transcript and provide a detailed answer using Anthropic's latest Claude Sonnet 4 model.

## Implementation Details

### 1. Claude Sonnet 4 Model Integration

Based on my web search, I found that the exact model name for Claude Sonnet 4 in the Anthropic API is:
- **Model Name**: `claude-sonnet-4-20250514`
- This is the latest Claude 4 model with high performance and exceptional reasoning capabilities
- It supports up to 200K tokens context window and 64K tokens maximum output

### 2. New Service: QuestionAnsweringService

Created `telegram_bot/services/question_answering_service.py` with the following functionality:

- **`QuestionAnsweringService`** class that uses Claude Sonnet 4 to answer questions about transcripts
- **`answer_question_about_transcript()`** method that creates detailed prompts for Claude to analyze transcripts
- **`read_transcript_file()`** method to safely read transcript content from files
- Comprehensive error handling and logging

### 3. Bot Integration

Modified `telegram_bot/bot.py` to support the new feature:

#### New Method: `handle_transcript_question()`
- Detects when a user replies to a transcript file with a question
- Downloads and reads the transcript content
- Sends the question and transcript to Claude Sonnet 4
- Returns formatted answers with proper message splitting for long responses
- Includes comprehensive error handling and progress messages

#### Updated Text Message Handler
- Renamed `handle_unsupported_message()` to `handle_text_message()`
- Added logic to detect transcript file replies and route them to the question handler
- Updated welcome message to inform users about the new feature

#### Enhanced Welcome Message
- Added information about the new transcript question feature
- Provided examples of questions users can ask
- Mentioned that answers are powered by Claude Sonnet 4

### 4. Configuration Updates

The codebase already had Claude support configured with the correct model name:
- **Config field**: `claude_model` (defaults to `claude-sonnet-4-20250514`)
- **Environment variable**: `CLAUDE_MODEL`
- **API key**: `ANTHROPIC_API_KEY`

## How It Works

1. **User uploads audio/video file** → Bot transcribes and sends transcript file
2. **User replies to transcript file with a question** → Bot detects this is a transcript question
3. **Bot downloads transcript content** → Reads the file safely
4. **Bot sends transcript + question to Claude Sonnet 4** → Uses detailed prompt for analysis
5. **Bot receives and formats answer** → Splits long responses if needed
6. **Bot sends formatted answer to user** → With question context and proper formatting

## Example Usage

1. User uploads an audio file of a meeting
2. Bot transcribes it and sends `transcript_20250101_123456.txt`
3. User replies to the transcript file with: "What were the main action items discussed?"
4. Bot analyzes the transcript using Claude Sonnet 4 and responds with detailed action items

## Features

- ✅ **Smart Detection**: Automatically detects when users reply to transcript files
- ✅ **Claude Sonnet 4 Integration**: Uses the latest and most capable Claude model
- ✅ **Detailed Prompting**: Provides comprehensive instructions to Claude for accurate analysis
- ✅ **Error Handling**: Robust error handling with user-friendly messages
- ✅ **Message Splitting**: Handles long responses by splitting them appropriately
- ✅ **Progress Feedback**: Shows users that the bot is processing their question
- ✅ **File Validation**: Ensures replies are to actual transcript files
- ✅ **Temporary File Cleanup**: Properly cleans up downloaded files

## Benefits

1. **Enhanced User Experience**: Users can now extract specific information from transcripts without manually reading through everything
2. **Powerful AI Analysis**: Claude Sonnet 4 provides intelligent, context-aware answers
3. **Seamless Integration**: Works naturally with existing transcript workflow
4. **Flexible Questions**: Users can ask any type of question about the transcript content
5. **Accurate Responses**: Claude Sonnet 4's advanced reasoning capabilities ensure high-quality answers

## Technical Notes

- The feature uses the existing AI model infrastructure with priority for Gemini, fallback to Claude
- Transcript files are identified by the filename pattern: `transcript_*.txt`
- The service handles both short and long responses appropriately
- Error messages guide users on how to resolve issues
- All temporary files are properly cleaned up after processing

This implementation provides users with a powerful way to interact with their transcribed content using state-of-the-art AI capabilities.