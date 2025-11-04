/**
 * Input sanitization utilities for the Echo application
 */
const logger = console;
export class InputSanitizer {
    // Allowed characters for different input types
    static ALLOWED_NAME_PATTERN = /^[a-zA-Z0-9\s\-_.]+$/;
    static ALLOWED_TEXT_PATTERN = /^[a-zA-Z0-9\s\-_.,!?'"()\n\r]+$/;
    // Dangerous patterns
    static SCRIPT_PATTERN = /<script[^>]*>.*?<\/script>/gi;
    static HTML_TAG_PATTERN = /<[^>]+>/g;
    static SQL_INJECTION_PATTERN = /\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b/i;
    /**
     * Sanitize chat message input
     */
    static sanitizeChatMessage(message) {
        if (!message || !message.trim()) {
            throw new Error("Message cannot be empty");
        }
        // Trim whitespace
        message = message.trim();
        // Remove script tags
        if (this.SCRIPT_PATTERN.test(message)) {
            logger.warn(`Script tag detected in message: ${message.slice(0, 100)}`);
            throw new Error("Invalid characters in message");
        }
        /* Check for SQL injection patterns (basic check)
        if (this.SQL_INJECTION_PATTERN.test(message)) {
            logger.warn(`Potential SQL injection detected: ${message.slice(0, 100)}`);
            throw new Error("Invalid characters in message");
        }*/
        // HTML escape (but preserve newlines and basic punctuation)
        message = this.htmlEscape(message);
        return message;
    }
    /**
     * Sanitize profile name input
     */
    static sanitizeProfileName(name) {
        if (!name || !name.trim()) {
            throw new Error("Name cannot be empty");
        }
        name = name.trim();
        // Only allow alphanumeric, spaces, hyphens, underscores, and periods
        if (!this.ALLOWED_NAME_PATTERN.test(name)) {
            throw new Error("Name contains invalid characters");
        }
        return name;
    }
    /**
     * Sanitize general text field input (for profile descriptions, etc.)
     */
    static sanitizeTextField(text) {
        if (!text) {
            return "";
        }
        text = text.trim();
        // Remove script tags
        if (this.SCRIPT_PATTERN.test(text)) {
            logger.warn("Script tag detected in text field");
            throw new Error("Invalid content detected");
        }
        // HTML escape
        text = this.htmlEscape(text);
        return text;
    }
    /**
     * Sanitize file path to prevent directory traversal
     */
    static sanitizeFilePath(path) {
        if (!path) {
            throw new Error("Path cannot be empty");
        }
        // Check for directory traversal
        if (path.includes('..') || path.startsWith('/')) {
            throw new Error("Invalid path");
        }
        // Only allow alphanumeric, hyphens, underscores, and periods
        if (!/^[a-zA-Z0-9\-_.]+$/.test(path)) {
            throw new Error("Path contains invalid characters");
        }
        return path;
    }
    /**
     * Validate that value is in allowed list
     */
    static validateEnum(value, allowedValues) {
        if (!allowedValues.includes(value)) {
            throw new Error(`Invalid value. Must be one of: ${allowedValues.join(', ')}`);
        }
        return value;
    }
    /**
     * Sanitize timezone string
     */
    static sanitizeTimezone(timezone) {
        if (!timezone || !timezone.trim()) {
            throw new Error("Timezone cannot be empty");
        }
        timezone = timezone.trim();
        // Allow alphanumeric, underscores, hyphens, and forward slashes (for timezones like America/New_York)
        if (!/^[a-zA-Z0-9/_\-]+$/.test(timezone)) {
            throw new Error("Timezone contains invalid characters");
        }
        return timezone;
    }
    /**
     * HTML escape helper
     */
    static htmlEscape(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '/': '&#x2F;',
        };
        return text.replace(/[&<>"'/]/g, (char) => map[char]);
    }
}
//# sourceMappingURL=sanitizer.js.map