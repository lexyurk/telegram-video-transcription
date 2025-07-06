# 📊 Product Analytics with PostHog

This guide explains how to set up and use PostHog for tracking product metrics in your Telegram Transcription Bot.

## 🎯 Why PostHog?

PostHog is the perfect choice for product analytics because:
- **🆓 Free Plan**: Up to 1M events per month
- **🚀 Zero Setup**: No database or infrastructure needed
- **📊 Beautiful Dashboard**: Built-in analytics dashboard
- **🔒 Privacy First**: GDPR compliant, can be self-hosted
- **📈 Real-time**: See metrics as they happen
- **🔧 Easy Integration**: Simple Python SDK

## 🛠️ Setup Instructions

### Step 1: Create PostHog Account
1. Go to [PostHog.com](https://posthog.com)
2. Sign up for a free account
3. Create a new project for your bot
4. Get your **API Key** from Project Settings

### Step 2: Install PostHog
```bash
pip install posthog
```

### Step 3: Configure Environment Variables
Add to your `.env` file:
```bash
# PostHog Analytics
POSTHOG_API_KEY=your_api_key_here
POSTHOG_HOST=https://app.posthog.com  # Optional, defaults to app.posthog.com
```

### Step 4: Run Your Bot
That's it! Analytics will start tracking automatically when you run your bot.

## 📊 What's Being Tracked

The analytics system automatically tracks all these events:

### 👥 User Events
- **Bot Started** - When users start your bot
- **Help Requested** - When users ask for help

### 📁 File Events
- **File Uploaded** - When users upload files
  - File name, size, type, extension
- **Transcription Started** - When transcription begins
- **Transcription Completed** - When transcription succeeds
  - Processing time, speed (MB/s)
- **Transcription Failed** - When transcription fails
  - Error messages for debugging
- **Summary Generated** - When AI summaries are created

### 🚫 Error Events
- **Unsupported File** - When users send unsupported files
  - Helps identify missing formats

## 🎨 Your PostHog Dashboard

Once you start using your bot, you'll see beautiful analytics in PostHog:

### 📈 Real-time Metrics
- **Active Users**: Who's using your bot right now
- **Event Volume**: How many events per hour/day
- **Success Rate**: How many transcriptions succeed vs fail
- **Processing Performance**: Average processing times

### 👥 User Analytics
- **User Retention**: How often users come back
- **Feature Usage**: Which features are most popular
- **User Journey**: How users interact with your bot
- **Cohort Analysis**: User behavior over time

### 📊 Product Insights
- **File Size Distribution**: What size files are most common
- **File Type Popularity**: Which formats are used most
- **Error Analysis**: What causes transcription failures
- **Performance Trends**: Is your bot getting faster/slower

## 🔍 Example Queries

PostHog lets you create custom insights. Here are some useful ones:

### 1. Daily Active Users
```
Event: Bot Started
Group by: Day
```

### 2. Success Rate Trend
```
Events: Transcription Completed vs Transcription Failed
Show as: Percentage
Group by: Day
```

### 3. Average Processing Time
```
Event: Transcription Completed
Property: processing_time_seconds
Aggregation: Average
Group by: Day
```

### 4. Popular File Types
```
Event: File Uploaded
Property: file_extension
Group by: file_extension
```

### 5. User Retention
```
Use PostHog's built-in Retention analysis
Starting event: Bot Started
Returning event: File Uploaded
```

## 🎯 Key Metrics to Monitor

### 📈 Growth Metrics
- **New Users**: How many new users per day/week
- **Active Users**: Daily/Weekly/Monthly active users  
- **User Retention**: How many users come back

### 📊 Product Metrics
- **Files Processed**: Total volume of transcriptions
- **Success Rate**: Percentage of successful transcriptions
- **Processing Speed**: Average time per file
- **File Size Distribution**: Understanding user behavior

### 🔧 Performance Metrics
- **Error Rate**: Track and fix common issues
- **Processing Time**: Monitor performance
- **File Type Usage**: Optimize for popular formats

## 📋 Setting Up Alerts

PostHog can send alerts when metrics change:

1. Go to **Insights** → **Alerts**
2. Create alerts for:
   - Success rate drops below 90%
   - Processing time increases significantly
   - Error rate increases
   - Daily active users drop

## 🔒 Privacy & Compliance

### What's Tracked
- **User IDs**: Telegram user IDs (hashed)
- **Events**: Actions users take
- **File Metadata**: Size, type, name (not content)
- **Performance**: Processing times, success/failure

### What's NOT Tracked
- **File Content**: Audio/video content is never sent
- **Personal Data**: Only basic user info (username, first name)
- **Transcription Content**: The actual transcripts aren't tracked

### GDPR Compliance
PostHog is GDPR compliant and provides:
- **Data Deletion**: Remove user data on request
- **Data Export**: Export user data
- **Anonymization**: User IDs are hashed
- **Opt-out**: Users can opt out of tracking

## 🚀 Advanced Features

### 1. Feature Flags
Use PostHog feature flags to:
- Test new features with subset of users
- Gradually roll out changes
- A/B test different approaches

### 2. Cohort Analysis
Understand user behavior:
- Power users vs casual users
- Users who use summaries vs transcripts only
- Users by file size preferences

### 3. Funnel Analysis
Track user journey:
1. Bot Started
2. File Uploaded
3. Transcription Completed
4. Return Usage

### 4. Custom Events
Track additional events:
```python
await self.analytics_service.track_custom_event(
    user_id, 
    "Feature Used", 
    {"feature": "speaker_identification"}
)
```

## 🔧 Troubleshooting

### Analytics Not Working?
1. **Check API Key**: Ensure `POSTHOG_API_KEY` is set correctly
2. **Check Internet**: PostHog needs internet access
3. **Check Logs**: Look for PostHog errors in bot logs
4. **Test Connection**: Events appear in PostHog within minutes

### No Data in Dashboard?
1. **Wait a few minutes**: Real-time data takes time to appear
2. **Check Date Range**: Ensure you're looking at the right time period
3. **Trigger Events**: Use your bot to generate test data

### Common Issues
- **"PostHog not installed"**: Run `pip install posthog`
- **"API key not set"**: Add `POSTHOG_API_KEY` to your `.env`
- **Rate limiting**: Free plan has generous limits, shouldn't be an issue

## 📊 Sample Dashboard

Here's what your PostHog dashboard will look like:

```
📈 OVERVIEW
├── 👥 Active Users (Today): 42
├── 📁 Files Processed: 156
├── ✅ Success Rate: 94.2%
└── ⏱️ Avg Processing: 45s

📊 TRENDS (7 days)
├── Daily Active Users: ↗️ +15%
├── Files per User: 3.2
├── Success Rate: 📈 94.2%
└── Processing Speed: ⚡ 1.2x faster

🔥 TOP EVENTS
├── File Uploaded: 156
├── Transcription Completed: 147
├── Bot Started: 42
└── Summary Generated: 134
```

## 🎯 Business Insights

PostHog helps you understand:

### 📈 Growth
- **User Acquisition**: How do users find your bot?
- **User Retention**: Do users come back?
- **Feature Adoption**: Which features are popular?

### 🔧 Product
- **Performance**: Is your bot getting faster?
- **Reliability**: Are success rates improving?
- **Usage Patterns**: When do users use your bot?

### 💰 Business
- **User Value**: Which users are most active?
- **Cost Optimization**: Are you processing efficiently?
- **Feature Priorities**: What should you build next?

## 📞 Support

### Resources
- **PostHog Docs**: [docs.posthog.com](https://docs.posthog.com)
- **PostHog Community**: [posthog.com/slack](https://posthog.com/slack)
- **Python SDK**: [github.com/PostHog/posthog-python](https://github.com/PostHog/posthog-python)

### Getting Help
1. Check PostHog documentation
2. Look at the analytics service code in `telegram_bot/services/analytics_service.py`
3. Test with the PostHog debug mode
4. Check PostHog's status page for service issues

---

## 🎉 You're All Set!

Your Telegram bot now has world-class product analytics! 

**Next steps:**
1. Sign up for PostHog (free)
2. Add your API key to `.env`
3. Run your bot and watch the magic happen
4. Build awesome features based on real user data

PostHog will help you understand your users, improve your product, and grow your bot with confidence! 🚀