"""
LLM Processor - Main orchestrator
Coordinates all LLM-related processing using modular components
"""
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from .llm_inference import LLMInference
from .prompt_builder import PromptBuilder
from .response_cleaner import ResponseCleaner
from .context_manager import ContextManager
from .crisis_detector import CrisisDetector
from .age_detector import AgeDetector
from .lorebook_generator import LorebookGenerator
from .character_loader import (
    load_default_character_profile,
    load_character_by_name,
    load_user_settings,
    format_character_profile
)

logger = logging.getLogger(__name__)


class LLMProcessor:
    """
    Main LLM processor that orchestrates:
    - Model inference (LLMInference)
    - Prompt construction (PromptBuilder)
    - Response cleaning (ResponseCleaner)
    - Context management (ContextManager)
    """

    def __init__(
            self,
            model_path: str,
            n_ctx: int = 4096,
            n_threads: int = 4,
            n_gpu_layers: int = 999,
            n_batch: int = 512,
            memory_service=None
    ):
        """
        Initialize LLM processor with all components

        Args:
            model_path: Path to GGUF model file
            n_ctx: Context window size
            n_threads: CPU threads
            n_gpu_layers: GPU layers (-1 = all)
            n_batch: Batch size for prompt processing
            memory_service: Optional vector memory service
        """
        self.model_path = Path(model_path)
        self.initialized = False

        # Core components (initialized in reload_character)
        self.llm_inference = LLMInference(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            n_batch=n_batch
        )

        self.prompt_builder: Optional[PromptBuilder] = None
        self.response_cleaner: Optional[ResponseCleaner] = None
        self.context_manager = ContextManager(memory_service=memory_service)
        self.crisis_detector = CrisisDetector()
        self.age_detector = AgeDetector()

        # Default character data (loaded by reload_character)
        self.default_character_name = None
        self.user_name = "User"

        # Cache for character-specific prompt builders and cleaners
        self._prompt_builder_cache: Dict[str, PromptBuilder] = {}
        self._response_cleaner_cache: Dict[str, ResponseCleaner] = {}
        self._character_data_cache: Dict[str, tuple] = {}
        self._formatted_profile_cache: Dict[str, str] = {}  # Cache for formatted character strings

    async def initialize(self):
        """Initialize the LLM model and load character profile"""
        try:
            # Load character first
            self.reload_character()

            # Initialize LLM model
            await self.llm_inference.initialize()

            self.initialized = True
            logger.info("✅ LLMProcessor initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize LLMProcessor: {e}", exc_info=True)
            self.initialized = False
            raise

    def reload_character(self):
        """Reload default character profile"""
        try:
            # Load default character data
            (
                character_profile,
                character_name,
                avoid_words,
                user_name,
                companion_type,
                character_gender,
                character_role,
                character_backstory,
                lorebook,
                personality_tags,
            ) = load_default_character_profile()

            # Store default character info
            self.default_character_name = character_name
            self.user_name = user_name

            # Create default PromptBuilder and ResponseCleaner
            # These will be used as templates
            logger.info(f"✅ Default character loaded")

        except Exception as e:
            logger.error(f"❌ Failed to reload default character: {e}", exc_info=True)
            raise

    def _load_character_data(self, character_name: Optional[str] = None) -> tuple:
        """
        Load character data with caching.

        Args:
            character_name: Name of character, or None for default

        Returns:
            Tuple of character data
        """
        # Use default if no character specified
        if not character_name:
            character_name = self.default_character_name

        # Check cache first
        if character_name in self._character_data_cache:
            return self._character_data_cache[character_name]

        # Load character data
        # Always use load_character_by_name to ensure we get the correct character
        # (load_default_character_profile ignores the character_name parameter)
        char_data = load_character_by_name(character_name)

        # Cache it
        self._character_data_cache[character_name] = char_data

        return char_data

    def _get_prompt_builder_for_character(self, character_name: Optional[str] = None) -> PromptBuilder:
        """
        Get or create a PromptBuilder for the specified character.
        Uses cache to avoid recreating builders.

        Args:
            character_name: Name of character, or None for default

        Returns:
            PromptBuilder instance for the character
        """
        # Use default if no character specified
        if not character_name:
            character_name = self.default_character_name

        # Check cache first
        if character_name in self._prompt_builder_cache:
            return self._prompt_builder_cache[character_name]

        # Load character data (cached)
        (
            character_profile,
            char_name,
            avoid_words,
            user_name,
            companion_type,
            character_gender,
            character_role,
            character_backstory,
            lorebook,
            personality_tags,
        ) = self._load_character_data(character_name)

        # Load user settings
        user_settings = load_user_settings()

        # Create PromptBuilder
        prompt_builder = PromptBuilder(
            character_profile=character_profile,
            character_name=char_name,
            character_gender=character_gender,
            character_role=character_role,
            character_backstory=character_backstory,
            avoid_words=avoid_words,
            user_name=user_name,
            companion_type=companion_type,
            user_gender=user_settings.get('userGender', 'non-binary'),
            user_species=user_settings.get('userSpecies', 'human'),
            user_timezone=user_settings.get('timezone', 'UTC'),
            user_backstory=user_settings.get('userBackstory', ''),
            user_preferences=user_settings.get('userPreferences', {}),
            major_life_events=user_settings.get('majorLifeEvents', []),
            shared_roleplay_events=user_settings.get('sharedRoleplayEvents', []),
            user_communication_boundaries=user_settings.get('communicationBoundaries', ''),
            lorebook=lorebook,
            personality_tags=personality_tags
        )

        # Cache it
        self._prompt_builder_cache[character_name] = prompt_builder

        logger.debug(f"Created PromptBuilder for character")
        return prompt_builder

    def _get_response_cleaner_for_character(self, character_name: Optional[str] = None) -> ResponseCleaner:
        """
        Get a ResponseCleaner for the specified character with caching.

        Args:
            character_name: Name of character, or None for default

        Returns:
            ResponseCleaner instance
        """
        # Use default if no character specified
        if not character_name:
            character_name = self.default_character_name

        # Check cache first
        if character_name in self._response_cleaner_cache:
            return self._response_cleaner_cache[character_name]

        # Load character data (cached)
        (
            _,
            char_name,
            avoid_words,
            user_name,
            _,
            _,
            _,  # character_role not needed for ResponseCleaner
            _,  # character_backstory not needed for ResponseCleaner
            _,  # lorebook not needed for ResponseCleaner
            _,  # personality_tags not needed for ResponseCleaner
        ) = self._load_character_data(character_name)

        # Create ResponseCleaner
        import re
        avoid_patterns = [
            re.compile(re.escape(phrase), re.IGNORECASE)
            for phrase in avoid_words
        ]

        cleaner = ResponseCleaner(
            character_name=char_name,
            user_name=user_name,
            avoid_patterns=avoid_patterns
        )

        # Cache it
        self._response_cleaner_cache[character_name] = cleaner

        return cleaner

    async def generate_response(
            self,
            text: str,
            conversation_history: List[Dict],
            emotion: str = 'neutral',
            emotion_data: Optional[Dict] = None,
            character_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a response to user input

        Args:
            text: User's message
            conversation_history: List of previous messages [{role, content}]
            emotion: Detected emotion label
            emotion_data: Full emotion analysis dict
            character_name: Name of character to use (None = default)

        Returns:
            Dict with 'response', 'emotion', and other metadata
        """
        if not self.initialized:
            raise RuntimeError("LLMProcessor not initialized. Call initialize() first.")

        # PRIORITY 0: CRISIS DETECTION (IMMEDIATE OVERRIDE)
        # Check for suicidal ideation or self-harm BEFORE any processing
        is_crisis, risk_level, intervention_message = self.crisis_detector.detect(text)

        if is_crisis:
            logger.warning(f"🚨 CRISIS DETECTED - Risk level: {risk_level}")
            logger.warning(f"   Returning intervention message immediately")
            return {
                'success': True,
                'response': intervention_message,
                'emotion': 'concern',
                'emotion_score': 'high',
                'type': 'crisis_intervention',
                'crisis_detected': True,
                'risk_level': risk_level
            }

        # PRIORITY 1: AGE RESTRICTION (DETECTION)
        # Check for underage content and flag for graceful redirection
        is_age_violation, _ = self.age_detector.detect(text)

        if is_age_violation:
            logger.warning(f"⚠️  AGE RESTRICTION VIOLATION DETECTED")
            logger.warning(f"   Will gracefully redirect to 25+ ages")

        try:
            # Get character-specific components
            prompt_builder = self._get_prompt_builder_for_character(character_name)
            response_cleaner = self._get_response_cleaner_for_character(character_name)

            # Get the actual character name (resolved from default if needed)
            char_name = character_name or self.default_character_name

            # 1. Fetch context from memory and web if available
            # Detect if this is a conversation starter (don't search for starters)
            is_starter = "[System: Generate a brief, natural conversation starter" in text

            memory_context = await self.context_manager.fetch_memory_context(
                query=text,
                character=char_name,
                user_name=self.user_name
            )

            search_context = await self.context_manager.fetch_web_context(text, is_starter=is_starter)

            # 2. Get generation parameters based on content
            guidance, max_tokens, temperature = prompt_builder._get_generation_params(
                text=text,
                emotion=emotion,
                conversation_history=conversation_history,
                emotion_data=emotion_data
            )

            # 3. Build the complete prompt
            prompt = prompt_builder._build_prompt(
                text=text,
                guidance=guidance,
                emotion=emotion,
                conversation_history=conversation_history,
                search_context=search_context,
                emotion_data=emotion_data,
                age_violation_detected=is_age_violation,
                memory_context=memory_context
            )

            # LOG FULL RAW PROMPT FOR DEBUGGING
            logger.info("=" * 80)
            logger.info(f"TOTAL PROMPT SIZE: {len(prompt)} chars (~{len(prompt)//4} tokens)")
            logger.info("=" * 80)

            logger.debug(f"Prompt length: {len(prompt)} chars")
            logger.debug(f"Generation params: max_tokens={max_tokens}, temp={temperature}")

            # 4. Generate response from LLM
            raw_response, tokens_generated = await self.llm_inference.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )

            logger.debug(f"Raw response: {tokens_generated} tokens")

            # 5. Clean the response
            cleaned_response = response_cleaner.clean(raw_response)

            logger.info(f"✅ Generated response: {len(cleaned_response)} chars, {tokens_generated} tokens")

            return {
                'success': True,
                'response': cleaned_response,
                'emotion': emotion,
                'emotion_score': emotion_data.get('intensity', 'unknown') if emotion_data else 'unknown',
                'type': 'response',
                'tokens': tokens_generated
            }

        except Exception as e:
            logger.error(f"❌ Error generating response: {e}", exc_info=True)
            return {
                'success': False,
                'response': "I apologize, but I encountered an error processing your message.",
                'emotion': 'neutral',
                'error': str(e)
            }

    async def generate_with_context(
            self,
            text: str,
            emotion_data: Optional[Dict] = None,
            conversation_history: Optional[List[Dict]] = None,
            search_context: Optional[str] = None,
            character_profile: Optional[Dict] = None,
            max_tokens_override: Optional[int] = None,
            temperature_override: Optional[float] = None,
            character_name: Optional[str] = None,
            request_id: Optional[str] = None,
            enable_memory: Optional[bool] = False,
            enable_web_search: Optional[bool] = False,
            web_search_api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a response with explicit context (for advanced API usage)

        Args:
            text: User's message
            emotion_data: Full emotion analysis dict
            conversation_history: List of previous messages
            search_context: Pre-fetched web search results
            character_profile: Character override (contains character_name if specified)
            max_tokens_override: Override generation max tokens
            temperature_override: Override generation temperature
            character_name: Name of character to use (None = default)
            request_id: Request ID for cancellation tracking (optional)

        Returns:
            Dict with 'text' and 'tokens_generated'
        """
        if not self.initialized:
            raise RuntimeError("LLMProcessor not initialized. Call initialize() first.")

        # Check for cancellation at start
        if request_id:
            from main import cancelled_requests
            if request_id in cancelled_requests:
                logger.info(f"🚫 Request cancelled before generation")
                cancelled_requests.discard(request_id)
                raise RuntimeError("Request cancelled by client")

        try:
            conversation_history = conversation_history or []

            # Check if character_profile was provided
            if not character_profile:
                logger.debug("[LLMProcessor] No character_profile provided, will load from disk")

            # Extract character name from character_profile if provided there
            if character_profile and 'character_name' in character_profile:
                character_name = character_profile['character_name']
            elif character_profile and 'characterName' in character_profile:
                character_name = character_profile['characterName']

            # CRITICAL FIX: If character_profile dict is provided, use it instead of loading from disk
            if character_profile and (character_profile.get('characterString') or character_profile.get('name')):
                logger.info("✅ Using character_profile data sent from Node.js (not loading from disk)")

                # Extract data from the provided character_profile dict
                char_name = character_profile.get('characterName', character_name or self.default_character_name)

                # Get or format character string (with caching to avoid redundant formatting)
                if character_profile.get('characterString'):
                    character_string = character_profile.get('characterString')
                else:
                    # Check cache first (use character name as key)
                    cache_key = char_name
                    if cache_key in self._formatted_profile_cache:
                        character_string = self._formatted_profile_cache[cache_key]
                        logger.debug(f"Using cached formatted profile for '{char_name}'")
                    else:
                        # Format and cache
                        character_string = format_character_profile(character_profile)
                        self._formatted_profile_cache[cache_key] = character_string
                        logger.debug(f"Formatted and cached profile for '{char_name}'")

                avoid_words = character_profile.get('avoidWords', [])
                companion_type = character_profile.get('companionType', 'friend')

                # Extract character metadata
                character_gender = character_profile.get('gender', 'unknown')
                character_role = character_profile.get('role', '')
                character_backstory = character_profile.get('backstory', '')
                tag_selections = character_profile.get('tagSelections', {})

                # Extract character boundaries (string with newlines → list)
                character_boundaries_str = character_profile.get('boundaries', '')
                character_boundaries = [b.strip() for b in character_boundaries_str.split('\n') if b.strip() and b.strip() != '-']

                # Extract additional character fields for identity chunks
                character_species = character_profile.get('species', 'Human')
                character_age = character_profile.get('age', 25)
                character_interests = character_profile.get('interests', '')

                # Extract user settings from character_profile (Node.js merged them in)
                user_name = character_profile.get('user_name', character_profile.get('userName', 'User'))
                user_gender = character_profile.get('user_gender', 'non-binary')
                user_species = character_profile.get('user_species', 'human')
                user_timezone = character_profile.get('user_timezone', 'UTC')
                user_backstory = character_profile.get('user_backstory', '')
                user_preferences = character_profile.get('user_preferences', {})
                major_life_events = character_profile.get('user_major_life_events', [])
                shared_roleplay_events = character_profile.get('shared_roleplay_events', [])
                user_communication_boundaries = character_profile.get('user_communication_boundaries', '')

                # Generate lorebook from tagSelections if they exist
                lorebook = character_profile.get('lorebook', {})
                if tag_selections and not lorebook:
                    lorebook_generator = LorebookGenerator()
                    lorebook = lorebook_generator.generate_lorebook_from_tags(
                        character_name=char_name,
                        companion_type=companion_type,
                        selected_tags=tag_selections
                    )
                    logger.debug(f"Generated lorebook with {len(lorebook.get('chunks', []))} chunks")

                # Create PromptBuilder directly from provided data
                prompt_builder = PromptBuilder(
                    character_profile=character_string,
                    character_name=char_name,
                    character_gender=character_gender,
                    character_role=character_role,
                    character_backstory=character_backstory,
                    avoid_words=avoid_words,
                    user_name=user_name,
                    companion_type=companion_type,
                    user_gender=user_gender,
                    user_species=user_species,
                    user_timezone=user_timezone,
                    user_backstory=user_backstory,
                    user_preferences=user_preferences,
                    major_life_events=major_life_events,
                    shared_roleplay_events=shared_roleplay_events,
                    user_communication_boundaries=user_communication_boundaries,
                    lorebook=lorebook,
                    personality_tags=tag_selections,  # Pass the dict, not a list
                    # V3 additions for identity chunks
                    character_species=character_species,
                    character_age=character_age,
                    character_interests=character_interests,
                    character_boundaries=character_boundaries
                )

                # Get response cleaner for this character
                response_cleaner = self._get_response_cleaner_for_character(char_name)
            else:
                # Fallback to loading from disk (legacy)
                logger.warning("⚠️  No character_profile provided, falling back to disk load")
                prompt_builder = self._get_prompt_builder_for_character(character_name)
                response_cleaner = self._get_response_cleaner_for_character(character_name)
                char_name = character_name or self.default_character_name

            # 1. Fetch memory context if not provided via search_context
            memory_context = await self.context_manager.fetch_memory_context(
                query=text,
                character=char_name,
                user_name=self.user_name,
                enable_memory_override=enable_memory
            )

            # 2. Fetch web search context if not already provided and user enabled it
            if not search_context:
                # Detect if this is a conversation starter (don't search for starters)
                is_starter = "[System: Generate a brief, natural conversation starter" in text
                search_context = await self.context_manager.fetch_web_context(
                    text=text,
                    is_starter=is_starter,
                    enable_web_search=enable_web_search,
                    api_key=web_search_api_key
                )

            # 3. Get generation parameters
            emotion = emotion_data.get('emotion', 'neutral') if emotion_data else 'neutral'
            guidance, max_tokens, temperature = prompt_builder._get_generation_params(
                text=text,
                emotion=emotion,
                conversation_history=conversation_history,
                emotion_data=emotion_data
            )

            # Apply overrides if provided
            if max_tokens_override:
                max_tokens = max_tokens_override
            if temperature_override is not None:
                temperature = temperature_override

            # 4. Build the complete prompt
            prompt = prompt_builder._build_prompt(
                text=text,
                guidance=guidance,
                emotion=emotion,
                conversation_history=conversation_history,
                search_context=search_context,  # Use provided search context
                emotion_data=emotion_data,
                memory_context=memory_context
            )

            # Calculate approximate token count (chars / 4 is rough estimate)
            approx_tokens = len(prompt) // 4
            logger.info(f"Context-aware prompt: {len(prompt)} chars (~{approx_tokens} tokens)")
            logger.info(f"Generation params: max_tokens={max_tokens}, temp={temperature}")

            # Log prompt length only (not content)
            logger.debug(f"Prompt length: {len(prompt)} chars")

            # 5. Generate response from LLM
            raw_response, tokens_generated = await self.llm_inference.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )

            # Check for cancellation after generation (before cleaning/returning)
            if request_id:
                from main import cancelled_requests
                if request_id in cancelled_requests:
                    logger.info(f"🚫 Request cancelled after generation (discarding result)")
                    cancelled_requests.discard(request_id)
                    raise RuntimeError("Request cancelled by client")

            # 6. Clean the response
            cleaned_response = response_cleaner.clean(raw_response)

            logger.info(f"✅ Context-aware generation: {len(cleaned_response)} chars, {tokens_generated} tokens")

            return {
                'text': cleaned_response,
                'tokens_generated': tokens_generated
            }

        except Exception as e:
            logger.error(f"❌ Error in generate_with_context: {e}", exc_info=True)
            raise

    async def generate_conversation_starter(self, character_name: Optional[str] = None) -> str:
        """
        Generate a brief conversation starter for the character

        Args:
            character_name: Name of the character (None = default)

        Returns:
            Conversation starter text
        """
        if not self.initialized:
            raise RuntimeError("LLMProcessor not initialized. Call initialize() first.")

        try:
            # Get character-specific components
            prompt_builder = self._get_prompt_builder_for_character(character_name)
            response_cleaner = self._get_response_cleaner_for_character(character_name)

            # Get the actual character name (resolved from default if needed)
            char_name = character_name or self.default_character_name

            # Build a minimal prompt for starter
            starter_text = f"[System: Generate a brief, natural conversation starter from {char_name}. Keep it under 2 sentences, engaging and in-character.]"

            guidance, max_tokens, temperature = prompt_builder._get_generation_params(
                text=starter_text,
                emotion='neutral',
                conversation_history=[],
                emotion_data=None
            )

            prompt = prompt_builder._build_prompt(
                text=starter_text,
                guidance=guidance,
                emotion='neutral',
                conversation_history=[],
                search_context=None,
                emotion_data=None,
                memory_context=None
            )

            raw_response, _ = await self.llm_inference.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )

            cleaned_starter = response_cleaner.clean(raw_response)

            logger.info(f"✅ Generated conversation starter: {len(cleaned_starter)} chars")
            return cleaned_starter

        except Exception as e:
            logger.error(f"❌ Error generating starter: {e}", exc_info=True)
            return f"Hey there! How's your day going?"
