# Enhanced Logging System

A robust, configurable logging system designed for enterprise applications, featuring colored output, automatic file generation, context management, and flexible configuration options.

## Features

### Core Features
- 🎨 Colored console output with level-based coloring
- 📁 Automatic log file generation with timestamps
- 🔄 Simultaneous console and file logging
- 🎚️ Dynamic log level management
- 🔇 Console output suppression
- 🌐 Unicode support
- ⚙️ YAML-based configuration
- 🎯 Function call tracing with decorators
- 📊 Contextual logging with extra parameters

### Advanced Features
- 🕒 Timestamp-based log file naming
- 📂 Automatic log directory creation
- 🔍 Debug-level function entry/exit logging
- 🚫 Selective console output suppression
- 🔄 Rotating file handlers
- 🎯 Per-logger configuration

## Installation

Clone the repository:
```bash
cd altanafinancechatbotdev
git clone <repository_url_here>
```

## Configuration

### 1. Create config.yml

Create `config/config.yml` in the project root:

```yaml
logging:
  level: DEBUG
  log_format: "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
  use_colors: true
  console:
    enabled: true
    level: DEBUG
  file:
    enabled: true
    base_path: logs
    level: DEBUG
    max_size: 10485760  # 10MB
    backup_count: 5
```

### 2. Directory Structure

```
📦custom_logging
 ┣ 📜__init__.py
 ┣ 📜app_logger.py
 ┣ 📜base_logger.py
 ┣ 📜decorators.py
 ┣ 📜example_usage.py
 ┣ 📜formatters.py
 ┣ 📜handlers.py
 ┣ 📜logger_manager.py
 ┣ 📜logger.py
 ┣ 📜README.md
 ┗ 📜utils.py
```

## Usage Examples

### 1. Basic Logging

```python
from custom_logging import AppLogger

logger = AppLogger(
    logger_name="my_app",
    level="DEBUG",
    use_colors=True
)

# Use different log levels
logger.debug("Debug message")  # Cyan
logger.info("Info message")    # Green
logger.warning("Warning")      # Yellow
logger.error("Error")         # Red
logger.critical("Critical")   # Bold Red

# Log with extra context
logger.info("Processing order", extra={"order_id": "OCR-9998237"})
```

### 2. Function Call Logging

```python
from custom_logging import AppLogger, log_function_call

logger = AppLogger("my_app")

@log_function_call
def process_data(data: dict) -> dict:
    logger.info("Processing started", extra={"data_id": data.get("id")})
    # Code here ...
    return processed_data
```

### 3. Console Suppression

```python
from custom_logging import AppLogger, suppress_console_logging

logger = AppLogger("my_app")

# Normal logging
logger.info("Visible in console and file")

# Suppress console output
with suppress_console_logging():
    logger.info("Only written to file")
    logger.warning("Also only in file")

# Back to normal
logger.info("Visible again")
```

### 4. Automatic Log File Generation

```python
# Log files are automatically created with pattern:
# logs/{logger_name}_{timestamp}.log

# Example:
logger = AppLogger("my_app")
# Creates: logs/my_app_20231223_120145.log

# Check current log file
print(f"Logging to: {logger.log_file}")
```

## Best Practices

1. **Logger Naming**
   - Use descriptive logger names
   - Follow module hierarchy
   ```python
   logger = AppLogger(f"{__package__}.{__name__}")
   ```

2. **Log Levels**
   - **DEBUG**: Detailed information for debugging
   - **INFO**: General operational events
   - **WARNING**: Unexpected but handled events
   - **ERROR**: Errors that prevent normal operation
   - **CRITICAL**: System-level failures

3. **Contextual Information**
   ```python
   logger.info("Processing order", extra={
       "order_id": "AW-92341",
       "customer": "XYZ Industries",
       "status": "pending"
   })
   ```

4. **Exception Handling**
   ```python
   try:
       # Code here ...
   except Exception as e:
       logger.error(
           "Operation failed",
           exc_info=True,
           extra={"operation": "process_data"}
       )
   ```

## Testing
Run the logging test:
```bash
python -m custom_logging.example_usage
```

## Contact

- **Author**: Tirso Gomez
- **Email**: tirso.gomez@gds.ey.com
- **Maintainer**: Tirso Gomez


        