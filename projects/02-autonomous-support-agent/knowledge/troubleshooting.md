# Troubleshooting

## The app is slow or not loading

First, check our status page for ongoing incidents. Then try a hard refresh (Ctrl+Shift+R)
and clear the cache. If the problem persists, note the time and your browser so support can
investigate.

## I didn't receive a notification email

Notification emails can be delayed by your mail provider. Check spam, confirm your email in
Settings -> Profile, and ensure notifications are enabled in Settings -> Notifications.

## Integration webhook is failing

Webhook failures are usually due to an expired secret or a 4xx from your endpoint. Open
Settings -> Integrations to see the last delivery attempt and its response code, then rotate
the secret if needed.
