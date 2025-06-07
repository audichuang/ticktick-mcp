# TickTick MCP Timezone Guide

## Understanding Timezone Handling

The TickTick MCP server accepts dates in ISO 8601 format with timezone offset. It's crucial to include the correct timezone offset to ensure tasks appear at the right time.

## Common Timezone Offsets

- **Taiwan (台灣)**: `+0800`
- **Japan (日本)**: `+0900`
- **China (中國)**: `+0800`
- **Singapore**: `+0800`
- **Korea**: `+0900`
- **UTC**: `+0000`
- **EST (US Eastern)**: `-0500` (or `-0400` during DST)
- **PST (US Pacific)**: `-0800` (or `-0700` during DST)

## Correct Format Examples

### Taiwan Time (UTC+8)
```
明天早上8點 → 2025-06-09T08:00:00+0800
今天下午3點 → 2025-06-08T15:00:00+0800
```

### Japan Time (UTC+9)
```
明日朝8時 → 2025-06-09T08:00:00+0900
今日午後3時 → 2025-06-08T15:00:00+0900
```

## Common Mistakes

❌ **Wrong**: Using UTC time when you mean local time
```
"明天早上8點" → 2025-06-09T08:00:00+0000  // This is 4PM Taiwan time!
```

✅ **Correct**: Using local timezone
```
"明天早上8點" → 2025-06-09T08:00:00+0800  // This is 8AM Taiwan time
```

## Tips for Claude Users

1. **Be explicit about timezone**: Say "台灣時間早上8點" or "8AM Taiwan time"
2. **Check the timezone offset**: Ensure it matches your location
3. **Use 24-hour format**: Less ambiguous than AM/PM

## Example Commands

### Creating a task for 8AM Taiwan time tomorrow:
```
Create a task "Morning meeting" due tomorrow at 8AM Taiwan time
```

### Creating a task with reminder 1 hour before:
```
Create a task "Doctor appointment" due 2025-06-10T14:00:00+0800 with reminder 1 hour before
```

## Debugging Timezone Issues

If your tasks appear at the wrong time:

1. Check the timezone offset in the ISO date string
2. Verify your local timezone setting
3. Remember that TickTick displays times in your account's timezone setting

## Technical Note

The MCP server passes the ISO 8601 datetime string directly to TickTick API without modification. TickTick will interpret the timezone offset and display the task in your account's configured timezone.