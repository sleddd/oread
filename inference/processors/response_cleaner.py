"""
Response Cleaner
Handles all text cleaning and post-processing of LLM outputs
"""
import re
import logging

logger = logging.getLogger(__name__)


class ResponseCleaner:
    """Cleans and post-processes LLM-generated text"""

    # Compiled cleaning patterns
    WHITESPACE_PATTERN = re.compile(r'\s+')
    PUNCTUATION_SPACING_PATTERN = re.compile(r'\s+([.,!?])')
    LEADING_PUNCTUATION_PATTERN = re.compile(r'^[.,!?\s]+')
    QUOTE_PATTERN = re.compile(r'^\s*["\']|["\']\s*$')

    # Remove meta-commentary and narrative descriptions about the text itself
    # This catches elaborate descriptions like "(The name comes as a gentle wave...)"
    # but preserves simple actions like "(smiles)" or "(reaches for your hand)"
    META_PARENTHETICAL_PATTERN = re.compile(
        r'\([^)]*(?:'
        r'The [a-z]+(?:\s+[a-z]+){2,}|'  # "The name comes as..." (3+ words after "The")
        r'sensing your|responds? with|responded with|responding with|'
        r'warm tone|soft tone|gentle tone|playful tone|seductive tone|'
        r'with a [a-z]+ tone|in a [a-z]+ tone|'
        r'says [a-z]+ly|whispers [a-z]+ly|murmurs [a-z]+ly|'
        r'hovers in|carries the|comes as|sets it in motion'
        r')[^)]*\)',
        re.IGNORECASE
    )

    # Remove square bracket meta-commentary (including incomplete brackets)
    BRACKET_PATTERN = re.compile(r'\[[^\]]*(?:\]|$)')

    # Remove meta-analysis commentary (e.g., "This message fulfills...", "This response addresses...")
    META_ANALYSIS_PATTERN = re.compile(
        r'\[?\s*(?:This message|This response|The message|The response)\s+(?:fulfills|addresses|meets|follows|satisfies)[^\]]*(?:\]|$)',
        re.IGNORECASE
    )

    # Remove meta-instructions (e.g., "DO NOT RESPOND", "AWAIT INPUT", "REPLY WITH", "END OF RESPONSE", etc.)
    META_INSTRUCTION_PATTERN = re.compile(
        r'\*\([^)]*(?:DO NOT|AWAIT|WAIT FOR|STOP HERE|REPLY WITH|END OF RESPONSE)[^)]*\)(?:\([^)]*\))?\*?',
        re.IGNORECASE
    )

    # Remove internal reasoning blocks (e.g., "*(CONSEQUENCE:)(...)*", "*(REASONING:)(...)")
    # This catches any labeled meta-reasoning about the model's choices and intentions
    # Match with or without trailing asterisk
    INTERNAL_REASONING_PATTERN = re.compile(
        r'\*\s*\(\s*(?:CONSEQUENCE|REASONING|ACTION|INTENTION|CHOICE|DECISION|ANALYSIS|THOUGHT|REFLECTION|EXPLAINATION|EXPLANATION):\s*\)\s*\([^)]*\)\s*\*?',
        re.IGNORECASE
    )

    # Remove NOTE/OBSERVATION style meta-commentary (e.g., "*(NOTE:) The response stays within...")
    # This catches any asterisk-wrapped label followed by explanatory text or bullet points
    # Updated to handle both single-line and multi-line explanations with bullet points
    NOTE_COMMENTARY_PATTERN = re.compile(
        r'\*\s*\(\s*(?:NOTE|OBSERVATION|EXPLANATION|EXPLAINATION|CONTEXT|CLARIFICATION|IMPORTANT|WARNING):\s*\)\s*\*?\s*(?:[^\n]*(?:\n\s*•[^\n]*)*)',
        re.IGNORECASE
    )

    # Remove meta-reasoning text that describes model decisions
    # Catches phrases like "I've chosen to", "My action has prioritized", "I'm choosing to"
    # This handles cases where the reasoning appears in regular parentheses
    META_REASONING_PATTERN = re.compile(
        r'\([^)]{0,500}(?:'
        r'I\'ve chosen to|I have chosen to|My action has|I\'m choosing to|I am choosing to|'
        r'This (?:choice|action|decision) (?:has|will|prioritizes)|'
        r'prioritized maintaining|prioritizing our|prioritizes|'
        r'(?:has|have) prioritized|'
        r'in order to (?:maintain|keep|continue|avoid)|'
        r'avoiding potential'
        r')[^)]{0,500}\)',
        re.IGNORECASE
    )

    # Remove emojis (all Unicode emoji characters EXCEPT hearts)
    # Heart emojis are preserved for goodnight messages and reciprocation
    EMOJI_PATTERN = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002500-\U00002BEF"  # chinese char
        u"\U00002702-\U000027B0"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u2640-\u2642"
        u"\u2600-\u2B55"
        u"\u200d"
        u"\u23cf"
        u"\u23e9"
        u"\u231a"
        u"\ufe0f"  # dingbats
        u"\u3030"
        "]+", flags=re.UNICODE
    )

    # Red heart emoji pattern only (to preserve for goodnight messages)
    HEART_PATTERN = re.compile(r'❤️')

    # Remove formatting artifacts like "*(REPLY WITH YOUR ACTION/RESPONSE TO NAME)( )(END OF RESPONSE)"
    # This catches malformed instruction artifacts with multiple parentheses
    FORMAT_ARTIFACT_PATTERN = re.compile(
        r'\*\s*\([^)]*(?:REPLY WITH|RESPOND WITH|ACTION/?RESPONSE)[^)]*\)\s*(?:\([^)]*\)\s*)*\*?',
        re.IGNORECASE
    )

    # Remove emotion metadata that leaks into responses
    # Matches patterns like "(low intensity)", "(high intensity)", "(very high intensity)", etc.
    # Also matches the emotion name before it if present: "feeling curiosity (low intensity)"
    EMOTION_METADATA_PATTERN = re.compile(
        r'(?:feeling|experiencing)\s+\w+\s+\(\s*(?:very\s+)?(?:low|high|moderate|medium)\s+intensity\s*\)|\(\s*(?:very\s+)?(?:low|high|moderate|medium)\s+intensity\s*\)',
        re.IGNORECASE
    )

    def __init__(self, character_name: str, user_name: str, avoid_patterns: list):
        """
        Initialize cleaner with character-specific settings

        Args:
            character_name: Name of the character
            user_name: Name of the user
            avoid_patterns: List of compiled regex patterns to remove
        """
        self.character_name = character_name
        self.user_name = user_name
        self.avoid_patterns = avoid_patterns

    def _remove_duplicates(self, text: str) -> str:
        """
        Remove consecutive duplicate text that sometimes appears in model output.

        For example: "Hello there. Hello there." -> "Hello there."

        Args:
            text: Input text that may contain duplicates

        Returns:
            Text with consecutive duplicates removed
        """
        if not text or len(text) < 20:
            return text

        # Split text into chunks and check for consecutive repetition
        words = text.split()
        if len(words) < 5:
            return text

        # Check for repeated sequences of various lengths (from half the text down to 5 words)
        max_sequence_len = min(len(words) // 2, 30)

        for seq_len in range(max_sequence_len, 4, -1):
            # Check if the last seq_len words repeat the previous seq_len words
            if len(words) >= seq_len * 2:
                first_half = ' '.join(words[-seq_len * 2:-seq_len])
                second_half = ' '.join(words[-seq_len:])

                # If we find a duplicate, remove the second occurrence
                if first_half == second_half:
                    return ' '.join(words[:-seq_len])

        return text

    def _truncate_to_sentences(self, text: str, max_sentences: int = 3) -> str:
        """
        Truncate text to a maximum number of sentences naturally

        Args:
            text: Input text to truncate
            max_sentences: Maximum number of sentences to keep (default: 3)

        Returns:
            Truncated text with complete sentences
        """
        if not text:
            return text

        # Split on sentence boundaries while preserving actions in parentheses
        # Match period, exclamation, or question mark followed by space/end
        # but not if it's inside parentheses (actions)
        sentence_pattern = re.compile(r'([.!?]+)(?=\s+[A-Z(]|\s*$)')

        parts = sentence_pattern.split(text)
        sentences = []
        current_sentence = ""

        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Text part
                current_sentence += part
            else:
                # Punctuation part
                current_sentence += part
                sentences.append(current_sentence.strip())
                current_sentence = ""

        # Add any remaining text as a sentence if it exists
        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        # Take only the first max_sentences
        if len(sentences) > max_sentences:
            result = ' '.join(sentences[:max_sentences])
            # Ensure it ends with proper punctuation
            if result and result[-1] not in '.!?':
                result += '.'
            return result

        return text

    def _flatten_nested_actions(self, text: str) -> str:
        """
        Flatten nested action parentheses into a single action.

        Example:
        "(chuckles softly, (takes your hand), (runs thumb over your knuckles))"
        becomes:
        "(chuckles softly, takes your hand, runs thumb over your knuckles)"

        Args:
            text: Input text with potential nested parentheses

        Returns:
            Text with flattened action parentheses
        """
        # Find action blocks that contain nested parentheses
        # Match outer parentheses that contain inner ones
        def flatten_match(match):
            content = match.group(1)
            # Remove all inner parentheses, keeping just the content
            flattened = re.sub(r'[()]', '', content)
            # Clean up extra commas and spaces
            flattened = re.sub(r',\s*,', ',', flattened)
            flattened = re.sub(r'\s+', ' ', flattened)
            return f"({flattened.strip()})"

        # Match parentheses that contain other parentheses
        # This pattern finds outer parens containing nested ones
        pattern = r'\(([^()]*\([^)]*\)[^()]*)\)'

        # Keep replacing until no more nested parens exist
        prev_text = None
        while prev_text != text:
            prev_text = text
            text = re.sub(pattern, flatten_match, text)

        return text

    def clean(self, text: str) -> str:
        """
        Apply all final cleaning steps to raw LLM output

        Args:
            text: Raw LLM output text

        Returns:
            Cleaned text ready for user
        """
        text = text.strip()

        # Check if this is a goodnight message or has heart emoji
        is_goodnight = bool(re.search(r'\b(?:good\s*night|goodnight|sleep\s*well|sweet\s*dreams)\b', text, re.IGNORECASE))
        has_heart_emoji = bool(self.HEART_PATTERN.search(text))

        # Preserve heart emojis by temporarily replacing them
        heart_placeholder = "<<<HEART_EMOJI>>>"
        hearts_found = []
        if has_heart_emoji or is_goodnight:
            # Save all heart emojis
            hearts_found = self.HEART_PATTERN.findall(text)
            # Replace with placeholder
            text = self.HEART_PATTERN.sub(heart_placeholder, text)

        # Remove all other emojis
        text = self.EMOJI_PATTERN.sub('', text)

        # Restore heart emojis
        if hearts_found:
            for heart in hearts_found:
                text = text.replace(heart_placeholder, heart, 1)

        # Flatten nested action parentheses
        text = self._flatten_nested_actions(text)

        # OPTIMIZED: Combine all meta-commentary removal into one pass
        # Build combined pattern from all meta-patterns
        if not hasattr(self, '_combined_meta_pattern'):
            # Cache combined pattern on first use
            meta_patterns = [
                self.INTERNAL_REASONING_PATTERN.pattern,
                self.NOTE_COMMENTARY_PATTERN.pattern,
                self.META_REASONING_PATTERN.pattern,
                self.META_PARENTHETICAL_PATTERN.pattern,
                self.META_ANALYSIS_PATTERN.pattern,
                self.BRACKET_PATTERN.pattern,
                self.META_INSTRUCTION_PATTERN.pattern,
                self.FORMAT_ARTIFACT_PATTERN.pattern,
                self.EMOTION_METADATA_PATTERN.pattern
            ]
            self._combined_meta_pattern = re.compile('|'.join(f'(?:{p})' for p in meta_patterns), re.IGNORECASE)

        text = self._combined_meta_pattern.sub('', text)

        # OPTIMIZED: Combine punctuation fixes into one pass
        if not hasattr(self, '_combined_punctuation_pattern'):
            # Cache combined pattern
            self._combined_punctuation_pattern = re.compile(
                r'(?P<spacing>\s+([.,!?]))|(?P<leading>^[.,!?\s]+)|(?P<quote>^\s*["\']|["\']\s*$)'
            )

        def punctuation_repl(match):
            if match.group('spacing'):
                return match.group(2)  # Remove space before punctuation
            elif match.group('leading') or match.group('quote'):
                return ''  # Remove leading punctuation or quotes
            return match.group(0)

        text = self._combined_punctuation_pattern.sub(punctuation_repl, text)

        # Remove stop sequences and turn markers
        stop_sequences = [
            f"\n{self.user_name}:", f"{self.user_name}:", "\nUser:", "User:",
            "\nHuman:", "Human:", "User Permissions:", "(emotion:", "[silence]",
            f"\n{self.character_name}:", f"{self.character_name}:",
            "### End of Conversation", "###",
            "*(END CURRENT CONTEXT)*", "(END CURRENT CONTEXT)",
            "((END RESPONSE))", "(END RESPONSE)", "**END RESPONSE**"
        ]

        for seq in stop_sequences:
            text = text.split(seq)[0].strip()

        # Remove character name prefix at start
        if text.startswith(f"{self.character_name}:"):
            text = text[len(f"{self.character_name}:"):].strip()

        # Clean up again
        text = text.strip()

        # OPTIMIZED: Combine avoid patterns, asterisk conversion, and final cleanup into one pass
        if not hasattr(self, '_combined_final_pattern'):
            # Combine avoid patterns with asterisk and quote patterns
            avoid_pattern_strs = [p.pattern for p in self.avoid_patterns] if self.avoid_patterns else []
            combined_patterns = avoid_pattern_strs + [
                self.LEADING_PUNCTUATION_PATTERN.pattern,
                self.QUOTE_PATTERN.pattern
            ]
            self._combined_final_pattern = re.compile('|'.join(f'(?:{p})' for p in combined_patterns))

        text = self._combined_final_pattern.sub('', text)

        # Convert *asterisks* to (parentheses) for frontend styling (needs separate pass for replacement)
        text = re.sub(r'\*([^*]+)\*', r'(\1)', text)

        # Remove duplicate consecutive text (sometimes models repeat themselves)
        text = self._remove_duplicates(text.strip())

        # Truncate to 2-3 sentences for more natural, concise responses
        text = self._truncate_to_sentences(text.strip(), max_sentences=3)

        # Add heart emoji to goodnight messages if not already present
        if is_goodnight and not self.HEART_PATTERN.search(text):
            # Add heart emoji to the end if it doesn't already have one
            text = text.rstrip() + ' ❤️'

        return text.strip()
