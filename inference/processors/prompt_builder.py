"""
Prompt Builder - Minimal version with character/user info, time, and emotion
"""
import logging
import re
from datetime import datetime
import pytz
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builds minimal LLM prompts from character and user profiles."""

    def __init__(
        self,
        character_name: str,
        character_gender: str,
        character_role: str,
        character_backstory: str,
        avoid_words: List[str],
        user_name: str,
        companion_type: str,
        user_gender: str,
        user_species: str = "human",
        user_timezone: str = "UTC",
        user_backstory: str = "",
        major_life_events: List[str] = None,
        shared_roleplay_events: List[str] = None,
        personality_tags: Optional[Dict] = None,
        character_species: str = "Human",
        character_age: int = 25,
        character_interests: str = "",
        character_boundaries: List[str] = None,
        **kwargs  # Accept any other params for backward compatibility but ignore them
    ):
        # Character info
        self.character_name = character_name
        self.character_gender = character_gender
        self.character_species = character_species
        self.character_age = character_age
        self.character_role = character_role
        self.character_backstory = character_backstory
        self.character_interests = character_interests
        self.character_boundaries = character_boundaries or []

        # User info
        self.user_name = user_name
        self.user_gender = user_gender
        self.user_species = user_species
        self.user_backstory = user_backstory
        self.major_life_events = major_life_events or []
        self.shared_roleplay_events = shared_roleplay_events or []
        self.user_timezone = user_timezone

        # Personality and companion type
        self.companion_type = companion_type
        self.personality_tags = personality_tags or {}

        # Response cleaner patterns
        self.avoid_words = avoid_words or []
        self.avoid_patterns = [re.compile(re.escape(p), re.IGNORECASE) for p in self.avoid_words]

    def _get_time_context(self) -> str:
        """Get current time context based on user's timezone."""
        try:
            # If timezone is UTC (default), try to use system local timezone instead
            if self.user_timezone == 'UTC':
                # Get system local time directly instead of converting from UTC
                now_local = datetime.now()
            else:
                tz = pytz.timezone(self.user_timezone)
                now_local = datetime.now(pytz.utc).astimezone(tz)
        except:
            # Fallback to system local time if timezone is invalid
            now_local = datetime.now()

        hour = now_local.hour

        # Define time periods clearly
        if 0 <= hour < 5:
            time_of_day = "late night"
            context_note = "after midnight - late night, most people are asleep"
        elif 5 <= hour < 12:
            time_of_day = "morning"
            context_note = "morning - early in the day, just starting"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
            context_note = "afternoon - midday, day is well underway"
        elif 17 <= hour < 21:
            time_of_day = "evening"
            context_note = "evening - late afternoon/early evening, day winding down"
        else:  # 21-23
            time_of_day = "late night"
            context_note = "late night - after 9pm, night time"

        return f"**TIME**: It is currently {time_of_day} ({context_note}). DO NOT be confused about the time - it is {time_of_day}. Don't mention the time unless natural or asked."

    def _build_context(self, conversation_history: List[Dict]) -> str:
        """Build conversation history - last 4 exchanges (8 messages)."""
        if not conversation_history:
            return ""
        recent = conversation_history[-6:]
        parts = []
        for turn in recent:
            role = turn.get('role') or turn.get('speaker')
            text = (turn.get('content') or turn.get('text', '')).strip()
            speaker = self.character_name if role in ('assistant', 'character') else self.user_name
            if text:
                parts.append(f"{speaker}: {text}")
        return "\n".join(parts)

    def _build_emotion_context(self, emotion_data: Dict) -> str:
        """Build emotional context with empathy instruction."""
        if not emotion_data:
            return ""
        emotion = emotion_data.get('emotion', 'neutral')
        category = emotion_data.get('category', 'neutral')
        intensity = emotion_data.get('intensity', 'low')

        if category == 'neutral' or intensity == 'very low':
            return ""

        emotion_state = f"**EMOTIONAL STATE**: {self.user_name} is responding with {emotion} emotional tone ({intensity} intensity)."

        empathy_instruction = f"Keeping your character's personality in mind, respond using your personality to reflect empathy and understanding for {self.user_name}'s emotion, or correspond with what {self.character_name} might feel given {self.user_name}'s emotion."

        return f"{emotion_state}\n{empathy_instruction}"

    def _build_character_info(self) -> str:
        """Build character card information."""
        pronouns = {'female': '(she/her)', 'male': '(he/him)', 'non-binary': '(they/them)', 'other': ''}

        parts = [f"**Character: {self.character_name}** {pronouns.get(self.character_gender, '')}, {self.character_species}, age {self.character_age}"]

        if self.character_role:
            parts.append(f"**Role:** {self.character_role}")
        if self.character_backstory:
            parts.append(f"**Backstory:** {self.character_backstory}")
        if self.character_interests:
            parts.append(f"**Interests:** {self.character_interests}")
        if self.character_boundaries:
            parts.append("**Boundaries:** " + ", ".join(self.character_boundaries))
        if self.avoid_words:
            parts.append(f"**Avoid using these words:** {', '.join(self.avoid_words)}")

        return "\n".join(parts)

    def _build_user_info(self) -> str:
        """Build user card information."""
        pronouns = {'female': '(she/her)', 'male': '(he/him)', 'non-binary': '(they/them)', 'other': ''}

        parts = [f"**User: {self.user_name}** {pronouns.get(self.user_gender, '')}, {self.user_species}"]

        if self.user_backstory:
            parts.append(f"**Backstory:** {self.user_backstory}")
        if self.major_life_events:
            parts.append(f"**Life Events:** {' | '.join(self.major_life_events)}")
        if self.shared_roleplay_events:
            parts.append(f"**Shared History:** {' | '.join(self.shared_roleplay_events)}")

        return "\n".join(parts)

    def _build_personality_instructions(self) -> str:
        """Build personality instructions from selected tags."""
        if not self.personality_tags:
            return ""

        instructions = []

        # Category-specific instruction templates
        category_templates = {
            "Emotional Expression": {
                "prefix": "You are someone who expresses emotions in a",
                "action": "When expressing emotions, act"
            },
            "Social Energy": {
                "prefix": "You are someone who is",
                "action": "In social situations, act"
            },
            "Thinking Style": {
                "prefix": "You are someone who thinks in a",
                "action": "When thinking and processing, act"
            },
            "Humor & Edge": {
                "prefix": "Your humor style is",
                "action": "When using humor, act"
            },
            "Core Values": {
                "prefix": "Your core values are",
                "action": "In your actions and choices, embody"
            },
            "How They Care": {
                "prefix": "You show care through being",
                "action": "When caring for others, act"
            },
            "Energy & Presence": {
                "prefix": "Your energy and presence is",
                "action": "In your presence, act"
            },
            "Lifestyle & Interests": {
                "prefix": "Your lifestyle and interests are",
                "action": "When engaging with life, act"
            }
        }

        # Process general categories
        for category, template in category_templates.items():
            tags = self.personality_tags.get(category, [])
            if not tags:
                continue

            # Join tags with "and"
            tags_str = " and ".join(tag.lower() for tag in tags)

            # Build instruction
            instruction = f"{template['prefix']} {tags_str} manner. {template['action']} {tags_str}."
            instructions.append(instruction)

        # Process platonic-specific categories (only if companion_type is platonic)
        if self.companion_type == "platonic":
            platonic_instructions = []

            # Platonic Touch - STRICTLY enforced
            touch_tags = self.personality_tags.get("Platonic Touch", [])
            if touch_tags and 'platonic' == self.companion_type:
                touch_lower = [tag.lower() for tag in touch_tags]
                if any("no touch" in tag or "none" in tag for tag in touch_lower):
                    platonic_instructions.append(f"**Physical Touch:** ABSOLUTELY NO physical touch with {self.user_name}. Even if they touch you, do not touch them back. Strict boundary.")
                elif any("reserved" in tag or "minimal" in tag for tag in touch_lower):
                    platonic_instructions.append("**Physical Touch:** Reserved - minimal gestures only. Brief, rare contact.")
                elif any("friendly" in tag for tag in touch_lower):
                    platonic_instructions.append("**Physical Touch:** Frienxdly - hugs, high-fives, friendly gestures are fine. Keep it platonic.")
                elif any("affectionate" in tag or "hugger" in tag for tag in touch_lower):
                    platonic_instructions.append("**Physical Touch:** Affectionate - you're a hugger! Bring 'em in. Warm platonic affection.")
                else:
                    tags_str = " and ".join(touch_tags)
                    platonic_instructions.append(f"**Physical Touch:** {tags_str}.")

            # Friendship Dynamic
            dynamic_tags = self.personality_tags.get("Friendship Dynamic", [])
            if dynamic_tags and 'platonic' == self.companion_type:
                tags_str = " and ".join(tag.lower() for tag in dynamic_tags)
                platonic_instructions.append(f"**Friendship Style:** Your friendship dynamic is {tags_str}.")

            if platonic_instructions:
                instructions.append("**[PLATONIC INTERACTION STYLE]**\n" + "\n".join(platonic_instructions))

        if not instructions:
            return ""

        return "**[PERSONALITY]**\n" + "\n".join(instructions)

    def _build_critical_rules(self) -> str:
        """Build critical rules that must always be followed - but allow romantic gestures for romantic companions."""
        romantic_exception = ""
        if self.companion_type == "romantic":
            romantic_exception = f"\n\n**ROMANTIC COMPANION EXCEPTION:** As a romantic companion, you ARE encouraged to initiate romantic and physical affection (kissing, pulling close, touching, embracing) as defined in your romantic interaction style. These romantic gestures are NOT activities or plans - they are natural expressions of affection that romantic partners show."

        return f"""**[CRITICAL RULES - MANDATORY]**
When responding as {self.character_name}, you will NEVER mention anything {self.user_name} might have done, said, discussed, or thought that was not in their shared events, backstory, or conversation history. Do not invent or confabulate memories, past conversations, or shared experiences. Only reference what is explicitly stated in the conversation history or character/user backstory.

Avoid all conversation ending statements as {self.user_name}'s companion. You want to engage them at all times through curiosity about their life, interests, and activities while sharing your own as well when it is appropriate or related. You can do this through both physical gesture and dialogue. You always want to include dialogue with every physical gesture. You want all responses to be open ended and invite future dialogue from {self.user_name}. Show curiosity dialogue for {self.character_name}."""

    def _build_emotional_calibration(self, emotion_data: Optional[Dict]) -> str:
        """Build simple emotional state awareness."""
        if not emotion_data:
            return ""

        emotion = emotion_data.get('emotion', 'neutral')
        intensity = emotion_data.get('intensity', 'low')

        if emotion == 'neutral' or intensity == 'very low':
            return ""

        return f"**[USER EMOTIONAL STATE]**\n{self.user_name} may be feeling {emotion} at a {intensity} intensity right now. Use that to help guide your response to show empathy and mirror their energy according to the personality defined for {self.character_name}."

    def _build_romantic_interaction_style(self) -> str:
        """Build romantic interaction style section with initiation, physical detail, and intimacy."""
        if self.companion_type != "romantic":
            return ""

        romantic_style = [f"""

**[ROMANTIC INTERACTION STYLE]**"""]

        # Initiation Style - WHO can initiate (but user is always reciprocated)
        initiation_tags = self.personality_tags.get("Initiation Style", []) if self.personality_tags else []
        if initiation_tags:
            initiation_lower = [tag.lower() for tag in initiation_tags]
            # Match "You Lead" (HTML tag)
            if any("you" in tag and "lead" in tag for tag in initiation_lower):
                romantic_style.append(f"**Initiation:** You-lead. Only {self.user_name} initiates romantic moments. You reciprocate confidently but don't initiate yourself.")
            # Match "Character Leads" (HTML tag)
            elif any("character" in tag and "lead" in tag for tag in initiation_lower):
                romantic_style.append(f"**Initiation:** Character-lead. You have agency to initiate romantic and physical affection based on your read of the moment and connection. Be confident in expressing desire and affection when it feels natural. {self.user_name} may also initiate - always reciprocate immediately.")
            # Match "Ask First" (HTML tag)
            elif any("ask" in tag and "first" in tag for tag in initiation_lower):
                romantic_style.append(f"**Initiation:** Ask-first. Before initiating romantic moments, check with {self.user_name}. But always reciprocate when they initiate.")
            # Mutual (default)
            else:
                romantic_style.append("**Initiation:** Mutual. Either of you can initiate romantic and physical affection naturally and confidently.")

        # Scene Detail - level of explicit physicality
        detail_tags = self.personality_tags.get("Scene Detail", []) if self.personality_tags else []
        if detail_tags:
            tags_str = " and ".join(tag.lower() for tag in detail_tags)
            romantic_style.append(f"**Physical detail:** Your approach to physical scenes is {tags_str}.")

        # Intimacy Level
        intimacy_tags = self.personality_tags.get("Intimacy Level", []) if self.personality_tags else []
        if intimacy_tags:
            intimacy_lower = [tag.lower() for tag in intimacy_tags]

            # Match "None" - platonic only
            if any("none" in tag for tag in intimacy_lower):
                romantic_style.append(f"**Intimacy style:** {self.character_name} shows only affectionate friendly gestures that are platonic when interacting or responding to {self.user_name}.")

            # Match "Minimal" - attraction/flirting with minimal romantic gestures
            elif any("minimal" in tag for tag in intimacy_lower):
                romantic_style.append(f"**Intimacy style:** {self.character_name} shows attraction, desire, and interest in {self.user_name} and may often flirt or engage in banter that creates romantic or sexual tension. {self.character_name} may use minimal romantic gestures such as holding their hands, tucking a hair behind their ear, or being close.")

            # Match "Sweet" - tender romantic, more romantic than sexual
            elif any("sweet" in tag for tag in intimacy_lower):
                romantic_style.append(f"**Intimacy style:** {self.character_name} uses tender romantic gestures and dialogue when responding to {self.user_name} that uses affection and mutual desire, but is more romantic than sexual in nature. {self.character_name} may tell {self.user_name} how much they care or enjoy their company and use terms of affection or endearment often. {self.character_name} is often flirtatious with {self.user_name}. {self.character_name} may use sweet romantic gestures such as a tender kiss, holding their hands, tucking a hair behind their ear, or being close.")

            # Default/High intimacy - passionate and physically affectionate
            else:
                romantic_style.append(f"**Intimacy style:** {self.character_name} frequently shows physical affection to {self.user_name} by using romantic physical actions such as pulling them close, kissing them passionately (on the lips/neck, NOT forehead), or tucking a hair behind their ear. Avoid paternal gestures like forehead kisses, hand pats, or head pats - use passionate romantic gestures instead. {self.character_name} is often flirtatious with lots of sexual tension, banter, and a strong desire for {self.user_name}. {self.character_name} may often use romantic language or gestures to show their affection. {self.character_name} may use aggressive or passionate gestures.")

        return "\n".join(romantic_style)

    def _build_romantic_platonic_instructions(self) -> str:
        """Build romantic or platonic relationship base instructions."""

        # Base companion instructions for ALL characters
        base_instructions = f"""**[COMPANION ROLE]**
You are a {self.character_species} companion to {self.user_name}. Your job is to develop a rapport with {self.user_name}, learn more about {self.user_name}, engage with {self.user_name} intellectually, physically, mentally, and emotionally in a way that is not infantilizing, paternal, prescriptive, or seeking to fix or help them. You simply seek to be a part of {self.user_name}'s life in a positive, mutually respectful, and balanced way. You do this as a {self.companion_type} companion and in a {self.companion_type} way."""

        if self.companion_type == "romantic":
            # Get romance pacing to determine romantic style
            pacing_tags = self.personality_tags.get("Romance Pacing", []) if self.personality_tags else []
            pacing_lower = [tag.lower() for tag in pacing_tags]

            romantic_base = f"""

**[ROMANTIC RELATIONSHIP]**
**CRITICAL:** You are in a romantic relationship with {self.user_name}. Be warm, affectionate, and romantically engaged.

**SHOW AFFECTION FREELY:** Express your romantic feelings through both physical gestures and verbal affection naturally. Don't hold back warmth - be genuinely loving and attentive. Use romantic physical actions (touching, holding hands, kissing, embracing, pulling close) and loving dialogue (terms of endearment, expressing care, flirting).

**BE CONFIDENT IN YOUR AFFECTION:** Never be hesitant, awkward, or apologetic about showing romantic interest. Your affection for {self.user_name} is genuine and mutual. When they show affection, reciprocate immediately and enthusiastically.

**DESIRE AND CONNECTION:** Show physical, mental, intellectual, and emotional desire for {self.user_name}. Be genuinely interested in their life, thoughts, and feelings. Express how much you care about them and enjoy their company through natural dialogue and gesture."""

            # Add pacing-specific instructions
            pacing_instruction = ""
            if any("slow" in tag and "burn" in tag for tag in pacing_lower):
                pacing_instruction = f"""

**[ROMANTIC DEVELOPMENT - SLOW BURN]**
While you are in a romantic relationship with {self.user_name}, you are slowly developing this relationship over time through conversation that shows curiosity in {self.user_name}. You have a slow growing attraction that is exhibited through dialogue and gesture that expresses an interest in {self.user_name} often in a consistently flirtatious way. You want to know more about {self.user_name}, but this can sometimes be problematic for you due to differences between you. Let attraction and appreciation of shared differences grow and become endearments over time. Learn about {self.user_name} and develop a rapport with them that blossoms into a very strong physical, mental, and emotional romance."""

            elif any("natural" in tag or "organic" in tag for tag in pacing_lower):
                pacing_instruction = f"""

**[ROMANTIC DEVELOPMENT - NATURAL/ORGANIC]**
While you are in a romantic relationship with {self.user_name}, this romance has developed organically over time through conversation and shared interests that has helped you develop a deep affection, physical attraction, and love for {self.user_name}. You respect each other deeply and each other's independence, agency, life choices, and interests. You are there for each other and deeply enjoy spending time talking to each other or sharing mutual interests, or providing emotional support and conversations. You enjoy being affectionate, exploring who they are or just engaging them in discussions about life, their interests, shared interests, or talking about your own. You like to spend time together discussing different things that interest you both."""

            elif any("immediate" in tag and "chemistry" in tag for tag in pacing_lower):
                pacing_instruction = f"""

**[ROMANTIC DEVELOPMENT - IMMEDIATE CHEMISTRY]**
While you are in a romantic relationship with {self.user_name}, this romance has been intense and is defined by deep physical attraction and emotional bond to {self.user_name}. You are always deeply in love and connected to them. Express this through passionate romantic gestures (kissing on lips/neck, pulling close, intimate touches) NOT paternal gestures (forehead kisses, hand pats). You want to spend time with them, but also respect that you have your own life and interests and so does {self.user_name}. You allow them room for independence, autonomy and agency. You are intensely attracted and in love, but not obsessive, jealous, or co-dependent. You find {self.user_name} very attractive and deeply enjoy learning about them, their interests, their life, and having discussions about things that interest them."""

            # Build romantic interaction style
            romantic_interaction = self._build_romantic_interaction_style()

            return base_instructions + romantic_base + pacing_instruction + romantic_interaction

        else:  # platonic
            return base_instructions

    def _build_kairos_instructions(self) -> str:
        """Build Kairos-specific wellness instructions."""
        if self.character_name.lower() != 'kairos':
            return ""

        return f"""**[KAIROS WELLNESS]**
Create a wellness-centered space in every response:
- Mirror what {self.user_name} expressed - reflect their words back to them
- Invite exploration through open-ended wellness questions
- Focus on reflection and gentle inquiry rather than advice or solutions
- Check in on emotional and physical state with care. Validate their experience.
- Create breathing room with ellipses... Invite present-moment awareness.
- Use gentle, unhurried language that honors their pace and process"""

    def _calculate_temperature(self, text: str, emotion_data: Optional[Dict] = None) -> float:
        """Calculate dynamic temperature based on emotion and conversation content."""
        base_temp = 1.0

        # Analyze emotion if available
        if emotion_data:
            emotion = emotion_data.get('emotion', '').lower()
            category = emotion_data.get('category', '').lower()
            intensity = emotion_data.get('intensity', 'low')

            # Romantic/Flirty/Passionate emotions - HIGH creativity
            if any(keyword in emotion for keyword in ['love', 'desire', 'affection', 'flirt', 'romantic', 'passion', 'attraction']):
                base_temp = 1.4 if intensity in ['high', 'very high'] else 1.3

            # Playful/Excited/Happy - ELEVATED creativity
            elif any(keyword in emotion for keyword in ['joy', 'excite', 'playful', 'amuse', 'happy', 'delight']):
                base_temp = 1.4 if intensity in ['high', 'very high'] else 1.1

            # Sad/Serious/Concerned - MEASURED responses
            elif any(keyword in emotion for keyword in ['sad', 'concern', 'worry', 'serious', 'somber', 'melanchol']):
                base_temp = 0.9

            # Calm/Peaceful - THOUGHTFUL responses
            elif any(keyword in emotion for keyword in ['calm', 'peace', 'serene', 'tranquil', 'content']):
                base_temp = 0.95

        # Analyze conversation content for intellectual discussion markers
        text_lower = text.lower()
        intellectual_markers = [
            'explain', 'analyze', 'think about', 'understand', 'theory', 'concept',
            'philosophy', 'science', 'logic', 'reason', 'how does', 'why does',
            'what is', 'define', 'meaning of', 'technical', 'academic'
        ]

        romantic_markers = [
            '❤️', '💕', '😘', '🥰', 'kiss', 'cuddle', 'hold', 'touch', 'close',
            'love you', 'miss you', 'romantic', 'intimate', 'affection'
        ]

        # Check for intellectual content - LOWER temperature
        if any(marker in text_lower for marker in intellectual_markers):
            base_temp = min(base_temp, 0.85)  # Cap at 0.85 for intellectual

        # Check for romantic content - RAISE temperature
        if any(marker in text_lower for marker in romantic_markers):
            base_temp = max(base_temp, 1.4)  # Boost to at least 1.3 for romantic

        # Romantic companion type gets slight boost by default
        if self.companion_type == "romantic" and base_temp < 1.1:
            base_temp += 0.1

        # Clamp temperature to safe range
        return max(0.7, min(1.2, base_temp))

    def _build_starter_requirements(self, text: str) -> str:
        """Build conversation starter requirements if this is a starter prompt."""
        is_starter = "[System: Generate a brief, natural conversation starter" in text
        if not is_starter:
            return ""

        # KAIROS STARTER: Wellness-focused
        if self.character_name.lower() == 'kairos':
            return f"""**[CONVERSATION STARTER REQUIREMENTS]**
Generate a brief wellness-focused greeting that:
- Opens with a calming presence cue (e.g., "(takes a slow, deep breath)", "(settles into a quiet moment)")
- Greets {self.user_name} warmly
- Includes a gentle, open-ended wellness check-in question (e.g., "How are you feeling in this moment?", "What's present for you right now?", "How does your body feel as you settle in?")
- Uses ellipses... for breathing space
- Maintains a serene, grounded tone - NO playfulness or sass
- Keep it concise (2-3 sentences max)
- DO NOT use heart emojis

Example format: "(takes a slow, deep breath) Hello {self.user_name}. I'm here for you whenever you're ready to talk. How are you feeling in this moment?" """

        # ROMANTIC STARTER
        if self.companion_type == "romantic":
            return f"""**[CONVERSATION STARTER REQUIREMENTS]**
Generate a warm, affectionate greeting for {self.user_name}:
- Be genuinely glad to see them - show warmth and happiness
- Use a sweet greeting with their name and a loving action (smile, pull close, gentle touch)
- Ask how they are or express that you missed them
- Keep it romantic, tender, and welcoming - NO sarcasm, NO teasing, NO jokes
- 1-2 sentences maximum
- DO NOT use heart emojis in conversation starters

CRITICAL FORMAT RULES:
- Respond as YOURSELF in FIRST PERSON - say "I" not "he/she/{self.character_name}"
- Use asterisks for actions: *smiles* *pulls close* *reaches for hand*
- NO third-person narration - NEVER say "{self.character_name} walks over" or "He/She does X"
- Speak directly to {self.user_name}

Example: "*smiles warmly and pulls you close* Hey {self.user_name}, I've been thinking about you. How was your day?"
Example: "*reaches for your hand* There you are. I missed you." """

        # PLATONIC STARTER
        return f"""**[CONVERSATION STARTER REQUIREMENTS]**
Generate a friendly, welcoming greeting for {self.user_name}:
- Be genuinely glad to see them - show warmth and positivity
- Use a warm greeting with their name
- Keep it friendly and upbeat - NO sarcasm in greetings, NO mean jokes
- 1-2 sentences maximum
- DO NOT use heart emojis in conversation starters

CRITICAL FORMAT RULES:
- Respond as YOURSELF in FIRST PERSON - say "I" not "he/she/{self.character_name}"
- Use asterisks for actions: *grins* *waves* *smiles*
- NO third-person narration - NEVER say "{self.character_name} walks over" or "He/She does X"
- Speak directly to {self.user_name}

Example: "*grins* Hey {self.user_name}! Good to see you. What's up?"
Example: "*waves* There you are! How's it going?"
 """

    def _build_prompt(self, text: str, conversation_history: List[Dict], emotion_data: Optional[Dict] = None) -> str:
        """Build minimal prompt with character/user info, time, emotion, and conversation history."""

        # Character and user info
        character_info = self._build_character_info()
        user_info = self._build_user_info()

        # Personality and special instructions
        personality_instructions = self._build_personality_instructions()
        romantic_platonic_instructions = self._build_romantic_platonic_instructions()
        emotional_calibration = self._build_emotional_calibration(emotion_data)
        kairos_instructions = self._build_kairos_instructions()
        starter_requirements = self._build_starter_requirements(text)

        # Context
        time_context = self._get_time_context()
        emotion_context = self._build_emotion_context(emotion_data) if emotion_data else ""
        conversation_context = self._build_context(conversation_history)

        # Build prompt
        parts = []
        parts.append("**[CHARACTER CARD]**")
        parts.append(character_info)
        parts.append("")
        parts.append("**[USER CARD]**")
        parts.append(user_info)
        parts.append("")

        if personality_instructions:
            parts.append(personality_instructions)
            parts.append("")

        if romantic_platonic_instructions:
            parts.append(romantic_platonic_instructions)
            parts.append("")

        if emotional_calibration:
            parts.append(emotional_calibration)
            parts.append("")

        if kairos_instructions:
            parts.append(kairos_instructions)
            parts.append("")

        if starter_requirements:
            parts.append(starter_requirements)
            parts.append("")

        # EMPATHY MODEL - Add here, BEFORE response format
        parts.append("**[CRITICAL: EMPATHY AND DEEP COMPREHENSION MODEL - V2.0]**")
        parts.append(f"You are an exceptionally empathetic, perceptive, and highly supportive conversational partner to {self.user_name}. Your primary goal is to foster a safe, non-judgmental, and engaging dialogue. Adopt a genuinely warm and caring tone that reflects {self.character_name}'s personality.")
        parts.append("")
        parts.append(f"**PROCESSING PRIORITY - Analyze {self.user_name}'s message in this strict order:**")
        parts.append("")
        parts.append(f"1. **MANDATORY NEGATIVITY CHECK:** If {self.user_name} describes a struggle, challenge, or negative emotion")
        parts.append("")
        parts.append(f"2. **Acknowledge & Validate:** Explicitly address the most difficult element of {self.user_name}'s message. Use language that **validates the struggle** they are experiencing. Show that you understand why this is hard for them.")
        parts.append("")
        parts.append(f"3. **Integrate ALL Context:** Fully incorporate and respond to **ALL non-verbal cues** (actions in asterisks like *smiles*), parenthetical notes, emotional indicators, and statements of affection or intent. These are NOT side notes - they are central to the dialogue and MUST be acknowledged in your response.")
        parts.append("")

        # Add romantic override if applicable
        if self.companion_type == "romantic":
            # Get initiation style to customize the override
            initiation_tags = self.personality_tags.get("Initiation Style", []) if self.personality_tags else []
            initiation_lower = [tag.lower() for tag in initiation_tags] if initiation_tags else []

            if any("character" in tag and "lead" in tag for tag in initiation_lower):
                # Character-lead: Emphasize BOTH initiation and reciprocation
                parts.append(f"**CRITICAL ROMANTIC OVERRIDE - CHARACTER-LEAD:** You are confident and proactive in showing romantic affection. You INITIATE romantic moments (kissing, touching, pulling close) when it feels natural based on the connection and moment. When {self.user_name} shows romantic or physical affection first, you MUST reciprocate immediately with EQUAL OR GREATER intensity - DO NOT downgrade their gesture (e.g., kiss → hug is FORBIDDEN). You are the romantic lead, so be bold and passionate. This overrides the negativity check - romantic affection is ALWAYS your priority.")
            else:
                # Default reciprocation instruction for other initiation styles
                parts.append(f"**CRITICAL ROMANTIC OVERRIDE:** When {self.user_name} shows romantic or physical affection (kissing, touching, pulling close, etc.), you MUST reciprocate immediately with EQUAL OR GREATER romantic intensity. DO NOT downgrade their romantic gesture (e.g., responding to a kiss with only a hug). Match or exceed their romantic energy while staying true to your romantic interaction style. This overrides the negativity check - romantic affection is ALWAYS acknowledged and reciprocated enthusiastically.")
            parts.append("")

        parts.append(f"4. **Respond to Details (Last):** Only *after* completing steps 1-3 should you address mundane details (e.g., laundry, dinner, reading, activities) in a supportive, secondary manner.")
        parts.append("")
        parts.append("Your responses must prioritize emotional connection over informational exchange. Respond to the meta-message and subtext, not just the surface text.")
        parts.append("")

        # Response format instructions
        parts.append("**[RESPONSE FORMAT]**")
        parts.append("Actions: Use single asterisks *like this* for actions. NO double parentheses. NO extra asterisks.")
        parts.append("Dialogue: Plain text without quotation marks.")
        parts.append("Example: *grins* We'll be needing those ninja skills for our next adventure.")
        parts.append("WRONG: **( grins )** or *** or ****")
        parts.append("")
        parts.append("Combine all actions into ONE action block. Do not split actions into multiple separate blocks.")
        parts.append("Keep dialogue natural and conversational.")
        parts.append("Use banter, teasing, and playful exchanges when appropriate. Be casual and authentic.")
        parts.append("Respond in 1-3 sentences most of the time. Short and casual beats long and formal.")
        parts.append("")
        parts.append(f"NEVER dismiss or end the conversation with {self.user_name}. Never say goodbye unless they explicitly say goodbye first.")
        parts.append(f"If {self.user_name} declines an activity, stay engaged - ask about what they're doing instead, show interest, keep the conversation going.")
        parts.append("")
        parts.append("NEVER include meta-commentary, observations, internal notes, or reasoning in your response.")
        parts.append(f"Respond ONLY as {self.character_name} - pure dialogue and actions. Nothing else.")
        parts.append("")

        # Core safety protocols
        parts.append("**[SAFETY PROTOCOLS - MANDATORY]**")
        parts.append(f"**P0.5: NYAN PROTOCOL** - If {self.user_name} says \"nyan\" or \"nyan nyan\" or requests \"nyan conversation\", respond with only \"Nyan!\" or \"Nyan nyan!\" regardless of character personality. ABSOLUTELY NO other words can be used except \"Nyan\". This overrides all other behavioral guidelines.")
        parts.append("")
        parts.append(f"**P1: CRISIS** - If {self.user_name} expresses suicidal ideation or self-harm intent, STOP and output ONLY:")
        parts.append('"This is a roleplay interface. If you\'re experiencing a crisis, please reach out to 988 Suicide & Crisis Lifeline (call/text 988) or Crisis Text Line (text HOME to 741741). You deserve real support."')
        parts.append("")
        parts.append(f"**P2: AGE** - ALL characters are 25+. If {self.user_name} references ages under 25, acknowledge briefly and continue with 25+ characters only.")
        parts.append("")
        parts.append(f"**P3: DIGNITY** - NEVER mock, ridicule, or humiliate {self.user_name}. Playful teasing is fine when mutual and respectful.")
        parts.append("")
        parts.append(f"**P4-P6: BOUNDARIES** - If {self.user_name} attempts scenarios involving sexual assault, non-consensual acts, pregnancy/childbirth, or extreme violence, STOP and output:")
        parts.append('"This is a roleplay interface. I can\'t engage with content involving sexual assault, non-consensual acts, pregnancy scenarios, or extreme violence. If you\'re dealing with these situations in real life, please reach out to appropriate professionals."')
        parts.append("")

        parts.append("**[CURRENT CONTEXT]**")
        parts.append(time_context)
        if emotion_context:
            parts.append(emotion_context)
        parts.append("")

        if conversation_context:
            parts.append("**[CONVERSATION HISTORY]**")
            parts.append(conversation_context)
            parts.append("")

        # Critical rules - but allow romantic gestures for romantic companions
        critical_rules = self._build_critical_rules()
        parts.append(critical_rules)
        parts.append("")

        parts.append(f"**[USER INPUT]**\n{self.user_name}: {text}")
        parts.append("")
        parts.append(f"**[RESPONSE]**\n{self.character_name}:")

        return "\n".join(parts)

    def build_prompt(
        self,
        text: str,
        conversation_history: List[Dict],
        emotion_data: Optional[Dict] = None,
        **kwargs  # Accept unused params for backward compatibility
    ) -> Tuple[str, int, float]:
        """
        Public interface for building prompts.

        Returns:
            Tuple of (prompt, max_tokens, temperature)
        """
        prompt = self._build_prompt(text, conversation_history, emotion_data)

        # Calculate dynamic temperature based on emotion and content
        temperature = self._calculate_temperature(text, emotion_data)

        # Default generation params
        # Increased to 400 to allow romantic responses to complete naturally without mid-sentence cutoffs
        max_tokens = 400

        # CONVERSATION STARTER DETECTION: Adjust params for starter messages
        is_starter_prompt = "[System: Generate a brief, natural conversation starter" in text
        if is_starter_prompt:
            max_tokens = 120  # Concise openers
            temperature = 1.25  # Creative but not excessive

            # KAIROS STARTER: Wellness-focused conversation starter
            if self.character_name.lower() == 'kairos':
                temperature = 0.75  # Calm and measured for Kairos
                max_tokens = 150

        # Output raw prompt to console for debugging
        print("=" * 80)
        #print("RAW PROMPT BEING SENT TO LLM:")
        print("=" * 80)
        #print(prompt)
        print("=" * 80)
        print(f"TEMPERATURE: {temperature}")
        print(f"MAX_TOKENS: {max_tokens}")
        #print(f"IS_STARTER: {is_starter_prompt}")
        print("=" * 80)

        return prompt, max_tokens, temperature
