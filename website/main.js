// Main JavaScript entry point
console.log('Transcribiscie App initialized');

// Load configuration from environment variables
const config = {
  telegramBotUsername: import.meta.env.VITE_TELEGRAM_BOT_USERNAME,
  websiteUrl: import.meta.env.VITE_WEBSITE_URL
};

// Initialize Telegram bot link on homepage
document.addEventListener('DOMContentLoaded', function() {
  const botLink = document.getElementById('telegram-bot-link');

  if (botLink && config.telegramBotUsername) {
    // Remove @ if present for the URL
    const cleanUsername = config.telegramBotUsername.replace('@', '');
    botLink.href = `https://t.me/${cleanUsername}`;
    
    // Show the button
    botLink.style.display = 'inline-flex';
  } else if (botLink) {
    // Hide button if no valid bot username configured
    botLink.style.display = 'none';
    console.warn('VITE_TELEGRAM_BOT_USERNAME not configured');
  }
});

