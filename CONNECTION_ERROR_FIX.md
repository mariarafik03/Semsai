# SemsAI Connection Error - Root Cause Analysis & Fix

## Problem Summary
Application was showing "Connection error" on `localhost:56071` while HuggingFace server logs showed `200 OK` responses.

## Root Causes Identified

### 1. ❌ **Critical Issue: Missing AGENTS_URL Configuration**
**File**: `semsai-backend/server.js`
- The `/conversation/step` proxy endpoint was defaulting to `http://127.0.0.1:8000/agents/step`
- This localhost address doesn't exist when services run on HuggingFace Spaces separately
- **Fix**: Changed to use HuggingFace Space URL: `https://youssif12-semsai-agents.hf.space/agents/step`

### 2. ❌ **Missing Chat Endpoints**
**File**: `agents-api/main.py`
- Flutter app expects: `/chat/respond`, `/chat/status/{sessionId}`, `/chat/results/{sessionId}`
- These endpoints were NOT implemented, only `/chat/start` existed
- **Fix**: Added all missing endpoints as aliases or shims

### 3. ❌ **Incomplete CORS Configuration**
**Files**: 
- `agents-api/main.py`
- `semsai-backend/server.js`

Issues:
- Missing `expose_headers` in CORS (prevents browser from seeing response headers)
- Missing `options_handler` for CORS preflight requests
- Missing explicit max_age for preflight caching
- **Fix**: Added comprehensive CORS configuration with all required headers

### 4. ❌ **No Request Timeout Handling**
**Files**:
- `agents-api/main.py`
- `SemsAi/lib/features/chat/data/repo/conversation_service.dart`

- Long-running requests could hang indefinitely
- **Fix**: Added 30-35 second timeouts and proper timeout error handling

### 5. ❌ **Insufficient Error Logging**
**Files**: All backend services

- Generic error messages made debugging impossible
- **Fix**: Added detailed error logging with full stack traces

### 6. ⚠️ **SECURITY ALERT: Exposed API Key**
Your OpenAI API key was posted in plain text:
```
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
```
**ACTION REQUIRED**: 
1. Immediately delete/rotate this key in OpenAI dashboard
2. Never commit secrets to version control
3. Use environment variables on HuggingFace Spaces instead

## Changes Made

### 1. agents-api/main.py
✅ Added `asyncio` import
✅ Enhanced CORS with `expose_headers` and `max_age`
✅ Added OPTIONS handler for CORS preflight
✅ Added HEAD support to root endpoint
✅ Added timeout handling (25 seconds) in `_handle_step()`
✅ Added comprehensive error handling with full traceback
✅ Added missing `/chat/respond` endpoint
✅ Added missing `/chat/status/{session_id}` endpoint
✅ Added missing `/chat/results/{session_id}` endpoint
✅ Better error messages in Arabic and English

### 2. semsai-backend/server.js
✅ Enhanced CORS configuration:
   - Added explicit origin: '*'
   - Added all required methods
   - Added allowedHeaders
   - Added optionsSuccessStatus
✅ Added `express.urlencoded` middleware
✅ Added OPTIONS handler for all paths
✅ **Fixed AGENTS_URL**: Changed from `http://127.0.0.1:8000` to HuggingFace URL
✅ Added timeout: 30 seconds for axios requests
✅ Added detailed error response with URL and error details
✅ Added `/health` endpoint for diagnostics

### 3. SemsAi/lib/core/networking/api_client.dart
✅ Added 30-second timeout to all requests
✅ Added console logging for debugging
✅ Proper error propagation with rethrow

### 4. SemsAi/lib/features/chat/data/repo/conversation_service.dart
✅ Added 35-second timeout (slightly longer than backend)
✅ Detailed request logging
✅ Better response status logging
✅ Proper error messages

## How to Test

### 1. Test Backend Health
```bash
# Test agents-api
curl https://youssif12-semsai-agents.hf.space/
# Expected: {"message":"SemsAi Agents API running","status":"ok"}

# Test semsai-backend  
curl https://youssif12-semsai-backend.hf.space/health
# Expected: {"status":"ok","message":"SemsAi Backend API running",...}
```

### 2. Test CORS Preflight
```bash
curl -X OPTIONS https://youssif12-semsai-agents.hf.space/ -v
# Should see:
# access-control-allow-origin: *
# access-control-allow-methods: GET, POST, PUT, DELETE, OPTIONS
```

### 3. Test Chat Endpoint
```bash
curl -X POST https://youssif12-semsai-agents.hf.space/chat/start \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 4. Test Proxy
```bash
curl -X POST https://youssif12-semsai-backend.hf.space/conversation/step \
  -H "Content-Type: application/json" \
  -d '{"user_input":"test"}'
```

## Configuration Required

### Environment Variables (HuggingFace Spaces Settings)

**semsai-backend**:
- `MONGO_URI` ✓ (already set)
- `AGENTS_URL` ← **OPTIONAL** - Add if agents-api is on different URL

**agents-api**:
- `MONGO_URI` ✓ (already set)
- `OPENAI_API_KEY` - **MUST BE ROTATED** (exposed in plain text)

## Deployment Steps

### 1. Push changes to GitHub
```bash
git add .
git commit -m "Fix: Connection error issues and add missing endpoints"
git push
```

### 2. Restart HuggingFace Spaces
- agents-api: Click "Restart" to rebuild with new code
- semsai-backend: Click "Restart" to rebuild with new code
- Wait 2-3 minutes for services to start

### 3. Verify in browser
- Open `localhost:56071` (or wherever your Flutter web app is)
- Should now connect without "Connection error"
- Check browser console for detailed logs

## Monitoring

### Check logs for:
1. **agents-api** (HuggingFace logs):
   - Should see: `"Starting chat session with: https://youssif12-semsai-agents.hf.space/chat/start"`
   - Should see: `"response status: 200"`

2. **semsai-backend** (HuggingFace logs):
   - Should see: `"Proxying to agents service: https://youssif12-semsai-agents.hf.space/agents/step"`

3. **Browser console** (dev tools):
   - Should see: `"Starting chat session with: https://youssif12-semsai-agents.hf.space/chat/start"`
   - Should see: `"Start chat response status: 200"`

## Common Issues & Solutions

### Issue: Still getting "Connection error"
1. Check CORS headers in browser DevTools → Network tab
2. Look for `access-control-allow-origin` header in response
3. Check if timeout is being exceeded (requests taking >30s)

### Issue: 502 Bad Gateway
1. Services haven't restarted yet - wait 5 minutes
2. Check HuggingFace Space logs for startup errors
3. Verify MongoDB URI is correct

### Issue: Status code 500
1. Check error logs in HuggingFace
2. Look for Python traceback in agents-api logs
3. Verify AGENTS_URL is set correctly

## Architecture Overview

```
┌─────────────────┐
│  Flutter App    │
│  (localhost:    │
│   56071)        │
└────────┬────────┘
         │
         ├─► [HTTP Request] ──────┐
         │                         │
         ├─────────────────────────┼─────────────────────────────┐
         │                         │                             │
         ▼                         ▼                             ▼
    ┌──────────────────────┐  ┌────────────────────┐  ┌──────────────────┐
    │  semsai-backend      │  │  agents-api        │  │ semsai-backend   │
    │  (Authorization,     │  │  (AI Agents,       │  │ (Proxy to agents)│
    │   Data storage)      │  │   Chat logic)      │  │                  │
    │                      │  │                    │  │  /conversation/  │
    │  Port: 7860          │  │  Port: 7860        │  │   step ────┐     │
    │  /developers         │  │  /chat/start       │  │            │     │
    │  /users              │  │  /chat/respond     │  │            └────►│
    │  /compounds/map      │  │  /chat/status      │  │                  │
    │  /units/listings     │  │  /chat/results     │  └──────────────────┘
    │  /conversation/step  │  │  /recommendations  │
    │  ▲                   │  │  /agents/step      │
    │  │                   │  │                    │
    │  └──────────────────►│  │ ◄─────────────────┬┘
    │                      │  │                   │
    │  ◄──────────────────►│  └───────────────────┘
    │  (API calls)         │     (Proxy calls)
    │                      │
    │  MongoDB connection  │  MongoDB connection
    └──────────────────────┘  └────────────────────┘
            ▲                           ▲
            │                           │
            └───────────┬───────────────┘
                        │
                        ▼
                    ┌─────────────┐
                    │  MongoDB    │
                    │  Atlas      │
                    └─────────────┘
```

## Files Modified

1. ✅ `agents-api/main.py` - Added missing endpoints, CORS, timeout handling
2. ✅ `semsai-backend/server.js` - Fixed AGENTS_URL, CORS, error handling
3. ✅ `SemsAi/lib/core/networking/api_client.dart` - Added timeout and logging
4. ✅ `SemsAi/lib/features/chat/data/repo/conversation_service.dart` - Added timeout and logging

## Next Steps

1. **Rotate the exposed API key immediately**
2. Deploy these changes to HuggingFace Spaces
3. Test all endpoints in browser
4. Monitor logs for any remaining issues
5. Consider implementing proper session management for better chat experience
6. Add request/response logging middleware for production monitoring

---
**Last Updated**: March 1, 2026
**Status**: ✅ Complete - Ready for deployment
