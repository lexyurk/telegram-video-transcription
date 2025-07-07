# Diagram Service Fix - Mermaid CLI Configuration Issue

## Issue Summary

The Telegram transcription bot was failing to generate diagrams with the following error:
```
error: unknown option '--puppeteerConfig'
```

## Root Cause

The `DiagramService` was trying to use the `--puppeteerConfig` command line option with the `mmdc` (Mermaid CLI) command, but this option is not supported in the current version of the Mermaid CLI.

## Technical Details

### The Problem
- The code was passing `--puppeteerConfig` as a command line argument to `mmdc`
- This option was removed or never existed in the current version of `@mermaid-js/mermaid-cli`
- The Mermaid CLI expects configuration to be passed via a configuration file using `--configFile`

### Error Location
The error occurred in `telegram_bot/services/diagram_service.py` in the `_convert_mermaid_to_image` method at lines 253 and 287.

## Solution

### Changes Made

1. **Updated `_get_puppeteer_config()` method**:
   - Changed return type from `str` to `dict`
   - Return the configuration as a Python dictionary instead of JSON string

2. **Modified `_convert_mermaid_to_image()` method**:
   - Create a temporary JSON configuration file containing the Puppeteer settings
   - Use `--configFile` instead of `--puppeteerConfig`
   - Added proper cleanup for temporary configuration files
   - Maintained fallback mechanism for simpler command without config file

### Code Changes

```python
# Before (broken):
cmd = [
    "mmdc",
    "-i", mmd_file_path,
    "-o", output_path,
    "--puppeteerConfig", puppeteer_config  # This option doesn't exist
]

# After (fixed):
# Create temporary config file
puppeteer_config = self._get_puppeteer_config()
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as config_file:
    json.dump({"puppeteer": puppeteer_config}, config_file)
    config_file_path = config_file.name

cmd = [
    "mmdc",
    "-i", mmd_file_path,
    "-o", output_path,
    "--configFile", config_file_path  # Use config file instead
]
```

## Testing

A test script `test_diagram_fix.py` has been created to verify the fix works correctly. The script:
1. Initializes the DiagramService
2. Generates a diagram from a sample transcript
3. Verifies the output file is created
4. Cleans up temporary files

## Verification

To verify the fix works:

1. Run the test script:
   ```bash
   python test_diagram_fix.py
   ```

2. Check the bot logs for successful diagram generation instead of the previous error

## Benefits

- **Compatibility**: Now works with the current version of Mermaid CLI
- **Reliability**: Proper error handling and fallback mechanisms
- **Maintainability**: Uses the official configuration approach
- **Resource Management**: Proper cleanup of temporary files

## Notes

- The fix maintains backward compatibility by providing a fallback command without configuration
- All Puppeteer configuration settings are preserved and passed correctly
- The Chrome executable path detection remains unchanged
- Logging has been improved for better debugging

## Future Considerations

- Monitor for any future changes to the Mermaid CLI configuration format
- Consider adding configuration validation
- May want to cache configuration files for performance if generation becomes frequent