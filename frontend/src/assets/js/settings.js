// API Configuration (use CONFIG from config.js)
const API_BASE = CONFIG.API_BASE;
let currentProfileName = '';
let currentAvatarData = null; // Store base64 avatar data for CHARACTER

// Dark-themed notification system
function showNotification(message, type = 'info') {
    // Remove any existing notification
    const existing = document.getElementById('custom-notification');
    if (existing) {
        existing.remove();
    }

    // Create notification element
    const notification = document.createElement('div');
    notification.id = 'custom-notification';
    notification.textContent = message;

    // Style based on type
    const styles = {
        success: {
            background: 'linear-gradient(135deg, #1a4d2e 0%, #2d5f3f 100%)',
            border: '1px solid #3a7f5f',
            boxShadow: '0 8px 32px rgba(26, 77, 46, 0.4)'
        },
        error: {
            background: 'linear-gradient(135deg, #4d1a1a 0%, #5f2d2d 100%)',
            border: '1px solid #7f3a3a',
            boxShadow: '0 8px 32px rgba(77, 26, 26, 0.4)'
        },
        info: {
            background: 'linear-gradient(135deg, #1a2d4d 0%, #2d3f5f 100%)',
            border: '1px solid #3a5f7f',
            boxShadow: '0 8px 32px rgba(26, 45, 77, 0.4)'
        }
    };

    const style = styles[type] || styles.info;

    Object.assign(notification.style, {
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        background: style.background,
        color: '#e8f4f0',
        padding: '24px 32px',
        borderRadius: '12px',
        border: style.border,
        boxShadow: style.boxShadow,
        fontSize: '16px',
        fontWeight: '500',
        zIndex: '10000',
        maxWidth: '500px',
        textAlign: 'center',
        backdropFilter: 'blur(10px)',
        animation: 'fadeIn 0.3s ease-in-out'
    });

    // Add to page
    document.body.appendChild(notification);

    // Auto-remove after 2.5 seconds
    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease-in-out';
        setTimeout(() => notification.remove(), 300);
    }, 2500);
}

// Add CSS animations
if (!document.getElementById('notification-styles')) {
    const style = document.createElement('style');
    style.id = 'notification-styles';
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; transform: translate(-50%, -60%); }
            to { opacity: 1; transform: translate(-50%, -50%); }
        }
        @keyframes fadeOut {
            from { opacity: 1; transform: translate(-50%, -50%); }
            to { opacity: 0; transform: translate(-50%, -40%); }
        }
    `;
    document.head.appendChild(style);
}

// Timezone list
const TIMEZONES = [
    'UTC',
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'America/Anchorage',
    'Pacific/Honolulu',
    'Europe/London',
    'Europe/Paris',
    'Europe/Berlin',
    'Europe/Madrid',
    'Europe/Rome',
    'Asia/Tokyo',
    'Asia/Shanghai',
    'Asia/Hong_Kong',
    'Asia/Singapore',
    'Asia/Dubai',
    'Asia/Kolkata',
    'Australia/Sydney',
    'Australia/Melbourne',
    'Pacific/Auckland'
];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

async function initializeApp() {
    // Populate timezone dropdown
    populateTimezones();

    // Check consent status first
    await checkConsentStatus();

    // Add event listeners
    document.getElementById('echoProfile').addEventListener('change', function(e) {
        loadProfileData(e.target.value);
    });

    document.getElementById('newProfileBtn').addEventListener('click', createNewProfile);
    document.getElementById('deleteProfileBtn').addEventListener('click', deleteProfile);
    document.getElementById('saveBtn').addEventListener('click', saveProfile);
    document.getElementById('saveUserSettings').addEventListener('click', saveUserSettings);
    document.getElementById('changePasswordBtn').addEventListener('click', changePassword);
    document.getElementById('exportDataBtn').addEventListener('click', exportData);

    // Character avatar handlers
    document.getElementById('avatarUpload').addEventListener('change', handleAvatarUpload);
    document.getElementById('generateAvatarBtn').addEventListener('click', generateAvatar);

    // Major life events handlers
    document.getElementById('addLifeEventBtn').addEventListener('click', addLifeEvent);

    // Auto-save when default character changes
    document.getElementById('defaultCharacter').addEventListener('change', async function(e) {
        await saveDefaultCharacter(e.target.value);
    });

    // Delete conversations handlers
    document.getElementById('deleteConversationsBtn').addEventListener('click', deleteAllConversations);
    document.getElementById('deleteCharacterConversationsBtn').addEventListener('click', function() {
        const characterName = document.getElementById('echoProfile').value;
        if (!characterName) {
            alert('Please select a character profile first');
            return;
        }
        deleteCharacterConversations(characterName);
    });

    // Tag button handlers
    initializeTagButtons();

    // Load user settings
    await loadUserSettings();

    // Load profiles from API
    await loadProfilesList();

    // Load default character dropdown
    await loadDefaultCharacterDropdown();

    // Load active profile
    await loadActiveProfile();
}

function populateTimezones() {
    const select = document.getElementById('userTimezone');
    TIMEZONES.forEach(tz => {
        const option = document.createElement('option');
        option.value = tz;
        option.textContent = tz;
        select.appendChild(option);
    });

    // Try to detect user's timezone
    try {
        const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
        if (TIMEZONES.includes(userTz)) {
            select.value = userTz;
        }
    } catch (e) {
        console.log('Could not detect timezone');
    }
}

async function loadUserSettings() {
    try {
        const response = await CONFIG.fetch('/api/user-settings');
        if (response.ok) {
            const data = await response.json();
            document.getElementById('userName').value = data.userName || 'User';
            document.getElementById('userGender').value = data.userGender || 'non-binary';
            document.getElementById('userSpecies').value = data.userSpecies || 'human';
            if (data.timezone) {
                document.getElementById('userTimezone').value = data.timezone;
            }

            // Load new fields
            document.getElementById('userBackstory').value = data.userBackstory || '';
            document.getElementById('userCommunicationBoundaries').value = data.communicationBoundaries || '';

            // Load preferences
            const prefs = data.userPreferences || {};
            document.getElementById('userPrefMusic').value = Array.isArray(prefs.music) ? prefs.music.join(', ') : '';
            document.getElementById('userPrefBooks').value = Array.isArray(prefs.books) ? prefs.books.join(', ') : '';
            document.getElementById('userPrefMovies').value = Array.isArray(prefs.movies) ? prefs.movies.join(', ') : '';
            document.getElementById('userPrefHobbies').value = Array.isArray(prefs.hobbies) ? prefs.hobbies.join(', ') : '';
            document.getElementById('userPrefOther').value = prefs.other || '';

            // Load major life events
            const events = data.majorLifeEvents || [];
            loadMajorLifeEvents(events);

            // Load advanced features
            document.getElementById('enableMemoryToggle').checked = data.enableMemory || false;
            document.getElementById('enableWebSearchToggle').checked = data.enableWebSearch || false;
            document.getElementById('webSearchApiKey').value = data.webSearchApiKey || '';

            // Load default character (will be set after dropdown is populated)
            if (data.defaultActiveCharacter) {
                const defaultCharDropdown = document.getElementById('defaultCharacter');
                if (defaultCharDropdown) {
                    defaultCharDropdown.setAttribute('data-default-character', data.defaultActiveCharacter);
                }
            }

            // Roleplay events removed - using conversation history instead
        }
    } catch (error) {
        console.error('Error loading user settings:', error);
        document.getElementById('userName').value = 'User';
        document.getElementById('userGender').value = 'non-binary';
        document.getElementById('userSpecies').value = 'human';
    }
}

async function saveUserSettings() {
    const userName = document.getElementById('userName').value.trim();
    const userGender = document.getElementById('userGender').value;
    const userSpecies = document.getElementById('userSpecies').value.trim() || 'human';
    const timezone = document.getElementById('userTimezone').value;
    const userBackstory = document.getElementById('userBackstory').value.trim();
    const communicationBoundaries = document.getElementById('userCommunicationBoundaries').value.trim();

    if (!userName) {
        alert('Please enter your name');
        return;
    }

    // Parse preferences (convert comma-separated strings to arrays)
    const parseCommaSeparated = (value) => {
        return value ? value.split(',').map(item => item.trim()).filter(item => item) : [];
    };

    const userPreferences = {
        music: parseCommaSeparated(document.getElementById('userPrefMusic').value),
        books: parseCommaSeparated(document.getElementById('userPrefBooks').value),
        movies: parseCommaSeparated(document.getElementById('userPrefMovies').value),
        hobbies: parseCommaSeparated(document.getElementById('userPrefHobbies').value),
        other: document.getElementById('userPrefOther').value.trim()
    };

    // Collect major life events
    const majorLifeEvents = getMajorLifeEvents();

    // Collect advanced features
    const enableMemory = document.getElementById('enableMemoryToggle').checked;
    const enableWebSearch = document.getElementById('enableWebSearchToggle').checked;
    const webSearchApiKey = document.getElementById('webSearchApiKey').value.trim();

    // Get default character selection
    const defaultCharacter = document.getElementById('defaultCharacter').value;

    try {
        const response = await CONFIG.fetch('/api/user-settings', {
            method: 'POST',
            body: JSON.stringify({
                userName,
                userGender,
                userSpecies,
                timezone,
                userBackstory,
                communicationBoundaries,
                userPreferences,
                majorLifeEvents,
                enableMemory,
                enableWebSearch,
                webSearchApiKey,
                defaultActiveCharacter: defaultCharacter || null
            })
        });

        if (!response.ok) throw new Error('Failed to save user settings');

        updateStatusBanner('✅ Your settings saved successfully!', true);
        showNotification('✅ Your settings saved successfully!', 'success');
    } catch (error) {
        console.error('Error saving user settings:', error);
        updateStatusBanner('⚠️ Error saving your settings: ' + error.message, false);
        alert('Error saving settings: ' + error.message);
    }
}

async function loadProfilesList() {
    try {
        const response = await CONFIG.fetch('/api/profiles');
        if (!response.ok) throw new Error('Failed to fetch profiles');

        const profiles = await response.json();
        const select = document.getElementById('echoProfile');
        select.innerHTML = '<option value="">-- Select a Profile --</option>';

        profiles.forEach(profileName => {
            const option = document.createElement('option');
            option.value = profileName;
            option.textContent = profileName;
            select.appendChild(option);
        });

        updateStatusBanner('✅ Profiles loaded successfully', true);
    } catch (error) {
        console.error('Error loading profiles:', error);
        updateStatusBanner('⚠️ Error loading profiles: ' + error.message, false);
    }
}

async function loadDefaultCharacterDropdown() {
    try {
        const response = await CONFIG.fetch('/api/profiles');
        if (!response.ok) throw new Error('Failed to fetch profiles');

        const profiles = await response.json();
        const select = document.getElementById('defaultCharacter');
        select.innerHTML = '<option value="">-- No default (select manually each time) --</option>';

        profiles.forEach(profileName => {
            const option = document.createElement('option');
            option.value = profileName;
            option.textContent = profileName;
            select.appendChild(option);
        });

        // Set the selected value from the data attribute (set during loadUserSettings)
        const defaultChar = select.getAttribute('data-default-character');
        if (defaultChar) {
            select.value = defaultChar;
            console.log('Set default character dropdown to:', defaultChar);
        }
    } catch (error) {
        console.error('Error loading default character dropdown:', error);
    }
}

async function saveDefaultCharacter(characterName) {
    try {
        // CRITICAL: Load existing user settings first to preserve them
        const existingResponse = await CONFIG.fetch('/api/user-settings');
        if (!existingResponse.ok) throw new Error('Failed to load existing settings');

        const existingSettings = await existingResponse.json();

        // Merge: Keep all existing settings, only update defaultActiveCharacter
        const response = await CONFIG.fetch('/api/user-settings', {
            method: 'POST',
            body: JSON.stringify({
                ...existingSettings,
                defaultActiveCharacter: characterName || null
            })
        });

        if (!response.ok) throw new Error('Failed to save default character');

        showNotification('✅ Default character saved successfully!', 'success');
    } catch (error) {
        console.error('Error saving default character:', error);
        showNotification('⚠️ Error saving default character: ' + error.message, 'error');
    }
}

async function loadActiveProfile() {
    try {
        const response = await CONFIG.fetch('/api/active');
        if (response.ok) {
            const data = await response.json();
            if (data.active) {
                document.getElementById('echoProfile').value = data.active;
                await loadProfileData(data.active);
            } else {
                loadDefaultProfile();
            }
        } else {
            loadDefaultProfile();
        }
    } catch (error) {
        console.error('Error loading active profile:', error);
        loadDefaultProfile();
    }
}

function loadDefaultProfile() {
    currentProfileName = '';
    document.getElementById('echoProfile').value = '';
    document.getElementById('echoName').value = '';
    document.getElementById('echoGender').value = 'female';
    document.getElementById('echoSpecies').value = 'human';
    document.getElementById('echoAge').value = '';
    document.getElementById('echoRole').value = '';
    document.getElementById('echoCompanionType').value = 'friend';
    document.getElementById('echoAppearance').value = '';
    document.getElementById('echoTraits').value = '';
    document.getElementById('echoInterests').value = '';
    document.getElementById('echoBackstory').value = '';
    document.getElementById('echoBoundaries').value = '';
    document.getElementById('echoAvoidWords').value = '';
    clearAvatar();
    clearTagSelections();
}

function createNewProfile() {
    loadDefaultProfile();
    clearAvatar();
    updateStatusBanner('📝 Creating new profile. Enter a name and save.', false);
}

async function loadProfileData(profileName) {
    if (!profileName) {
        loadDefaultProfile();
        return;
    }

    try {
        const response = await CONFIG.fetch(`/api/profiles/${encodeURIComponent(profileName)}`);
        if (!response.ok) throw new Error('Failed to load profile');

        const profileData = await response.json();
        currentProfileName = profileName;

        // Extract character data from profile structure
        const profile = profileData.character || profileData;

        // Load the data into the form
        document.getElementById('echoName').value = profile.name || '';
        document.getElementById('echoGender').value = profile.gender || 'female';
        document.getElementById('echoSpecies').value = profile.species || 'human';
        document.getElementById('echoAge').value = profile.age || '';
        document.getElementById('echoRole').value = profile.role || '';
        document.getElementById('echoCompanionType').value = profile.companionType || 'friend';
        document.getElementById('echoAppearance').value = profile.appearance || '';
        document.getElementById('echoTraits').value = profile.traits || '';
        document.getElementById('echoInterests').value = profile.interests || '';
        document.getElementById('echoBackstory').value = profile.backstory || '';
        document.getElementById('echoBoundaries').value = profile.boundaries || '';
        document.getElementById('echoAvoidWords').value = profile.avoidWords || '';

        // Load tag selections if present
        if (profile.tagSelections) {
            loadTagSelections(profile.tagSelections);
        } else {
            clearTagSelections();
        }

        // Load avatar for this profile
        await loadAvatar(profileName);

        // NOTE: Do NOT set as active profile when just loading for editing
        // await setActiveProfile(profileName);

        updateStatusBanner('✅ Loaded profile: ' + profileName, true);
    } catch (error) {
        console.error('Error loading profile:', error);
        updateStatusBanner('⚠️ Could not load profile: ' + profileName, false);
        loadDefaultProfile();
    }
}

async function setActiveProfile(profileName) {
    try {
        await CONFIG.fetch('/api/active', {
            method: 'POST',
            body: JSON.stringify({ active: profileName })
        });
    } catch (error) {
        console.error('Error setting active profile:', error);
    }
}

function getCurrentFormData() {
    return {
        name: document.getElementById('echoName').value,
        gender: document.getElementById('echoGender').value,
        species: document.getElementById('echoSpecies').value || 'human',
        age: document.getElementById('echoAge').value,
        role: document.getElementById('echoRole').value,
        companionType: document.getElementById('echoCompanionType').value,
        appearance: document.getElementById('echoAppearance').value,
        traits: document.getElementById('echoTraits').value,
        interests: document.getElementById('echoInterests').value,
        backstory: document.getElementById('echoBackstory').value,
        boundaries: document.getElementById('echoBoundaries').value,
        avoidWords: document.getElementById('echoAvoidWords').value,
        tagSelections: getSelectedTags()
    };
}

async function saveProfile() {
    const formData = getCurrentFormData();
    const profileName = formData.name.trim();

    if (!profileName) {
        alert('Please enter a name for your profile');
        return;
    }

    try {
        // Load existing profile to preserve favorites and other metadata
        let existingProfile = null;
        try {
            const existingResponse = await CONFIG.fetch(`/api/profiles/${encodeURIComponent(profileName)}`);
            if (existingResponse.ok) {
                existingProfile = await existingResponse.json();
            }
        } catch (err) {
            // Profile doesn't exist yet - that's fine
        }

        // Merge form data with existing profile to preserve favorites
        // Extract the character data if it's in v2.0 format
        const existingCharacter = existingProfile?.character || existingProfile;

        const profileData = existingProfile ? {
            ...formData,
            // Explicitly preserve favorites from existing profile
            favorites: existingCharacter.favorites || []
        } : formData;

        const response = await CONFIG.fetch(`/api/profiles/${encodeURIComponent(profileName)}`, {
            method: 'POST',
            body: JSON.stringify(profileData)
        });

        if (!response.ok) throw new Error('Failed to save profile');

        currentProfileName = profileName;

        // Save avatar if present
        await saveAvatar(profileName);

        // Reload profiles list and select this one
        await loadProfilesList();
        document.getElementById('echoProfile').value = profileName;

        // Set as active profile
        await setActiveProfile(profileName);

        updateStatusBanner('✅ Profile "' + profileName + '" saved successfully!', true);
        showNotification('✅ Profile "' + profileName + '" saved successfully!', 'success');
    } catch (error) {
        console.error('Error saving profile:', error);
        updateStatusBanner('⚠️ Error saving profile: ' + error.message, false);
        alert('Error saving profile: ' + error.message);
    }
}

async function deleteProfile() {
    const profileName = document.getElementById('echoProfile').value;

    if (!profileName) {
        alert('Please select a profile to delete');
        return;
    }

    if (!confirm(`Are you sure you want to delete the profile "${profileName}"?`)) {
        return;
    }

    try {
        const response = await CONFIG.fetch(`/api/profiles/${encodeURIComponent(profileName)}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete profile');

        updateStatusBanner('✅ Profile "' + profileName + '" deleted successfully', true);

        // Reload profiles and clear form
        await loadProfilesList();
        loadDefaultProfile();
    } catch (error) {
        console.error('Error deleting profile:', error);
        updateStatusBanner('⚠️ Error deleting profile: ' + error.message, false);
        alert('Error deleting profile: ' + error.message);
    }
}

function updateStatusBanner(message, isSuccess = false) {
   /* const banner = document.getElementById('statusBanner');
    banner.textContent = message;
    banner.classList.remove('success', 'error');
    if (isSuccess) {
        banner.classList.add('success');
    } else if (message.includes('Error') || message.includes('⚠️')) {
        banner.classList.add('error');
    }*/
}

function exportToPython() {
    const formData = getCurrentFormData();
    const companion = formData.companionType === 'friend' ? 'Platonic' : 'Romantic';

    const pythonString = 'CHARACTER_PROFILE = """\nName: ' + formData.name +
        '\nGender: ' + formData.gender +
        '\nAge: ' + formData.age +
        '\nRole: ' + formData.role +
        '\nCompanion Type: ' + companion +
        '\n\nAppearance:\n' + formData.appearance +
        '\n\nPersonality Traits:\n' + formData.traits +
        '\n\nPersonal Interests/Domains of Expertise:\n' + formData.interests +
        '\n\nBackstory:\n' + formData.backstory +
        '\n\nCommunication Style:\n' + formData.communicationStyle +
        '\n\nAffection Style:\n' + formData.affectionStyle +
        '\n\nCommunication Boundaries:\n' + formData.boundaries +
        '\n\nWords/Phrases to Avoid:\n' + formData.avoidWords +
        '\n"""';

    downloadFile(pythonString, (formData.name || 'profile') + '_character.py', 'text/plain');
}

function exportToText() {
    const formData = getCurrentFormData();
    const textContent = '[CHARACTER_PROFILE]\n' +
        'name=' + formData.name.replace(/\n/g, '\\n') + '\n' +
        'gender=' + formData.gender + '\n' +
        'age=' + formData.age + '\n' +
        'role=' + formData.role.replace(/\n/g, '\\n') + '\n' +
        'companionType=' + formData.companionType + '\n' +
        'appearance=' + formData.appearance.replace(/\n/g, '\\n') + '\n' +
        'traits=' + formData.traits.replace(/\n/g, '\\n') + '\n' +
        'interests=' + formData.interests.replace(/\n/g, '\\n') + '\n' +
        'backstory=' + formData.backstory.replace(/\n/g, '\\n') + '\n' +
        'communicationStyle=' + formData.communicationStyle.replace(/\n/g, '\\n') + '\n' +
        'affectionStyle=' + formData.affectionStyle.replace(/\n/g, '\\n') + '\n' +
        'boundaries=' + formData.boundaries.replace(/\n/g, '\\n') + '\n' +
        'avoidWords=' + formData.avoidWords.replace(/\n/g, '\\n');

    downloadFile(textContent, (formData.name || 'profile') + '_character.txt', 'text/plain');
}

function importFromText(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        const lines = content.split('\n');
        const profile = {};

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (line.includes('=')) {
                const firstEquals = line.indexOf('=');
                const key = line.substring(0, firstEquals).trim();
                const value = line.substring(firstEquals + 1).replace(/\\n/g, '\n');
                profile[key] = value;
            }
        }

        // Load the imported data into the form
        if (profile.name !== undefined) document.getElementById('echoName').value = profile.name;
        if (profile.gender) document.getElementById('echoGender').value = profile.gender;
        if (profile.age !== undefined) document.getElementById('echoAge').value = profile.age;
        if (profile.role !== undefined) document.getElementById('echoRole').value = profile.role;
        if (profile.companionType) document.getElementById('echoCompanionType').value = profile.companionType;
        if (profile.appearance !== undefined) document.getElementById('echoAppearance').value = profile.appearance;
        if (profile.traits !== undefined) document.getElementById('echoTraits').value = profile.traits;
        if (profile.interests !== undefined) document.getElementById('echoInterests').value = profile.interests;
        if (profile.backstory !== undefined) document.getElementById('echoBackstory').value = profile.backstory;
        if (profile.boundaries !== undefined) document.getElementById('echoBoundaries').value = profile.boundaries;
        if (profile.avoidWords !== undefined) document.getElementById('echoAvoidWords').value = profile.avoidWords;

        updateStatusBanner('✅ Profile imported successfully! Click Save to store it.', true);
    };
    reader.readAsText(file);
}

function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Avatar handling functions
function handleAvatarUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        alert('Please select an image file');
        return;
    }

    // Store the File object directly instead of converting to base64
    currentAvatarData = file;

    // Create a preview URL for display
    const previewUrl = URL.createObjectURL(file);
    displayAvatar(previewUrl);
}

async function generateAvatar() {
    const appearance = document.getElementById('echoAppearance').value;
    const name = document.getElementById('echoName').value;
    const gender = document.getElementById('echoGender').value;

    if (!appearance && !name) {
        alert('Please provide a name or appearance description to generate an avatar');
        return;
    }

    const prompt = appearance || `A ${gender} avatar for ${name}`;

    try {
        // For now, create a simple generated avatar using initials or placeholder
        // You can replace this with an actual AI image generation API call later
        alert('Avatar generation feature coming soon! For now, please upload an image.');

        // Placeholder: Generate a simple colored circle with initials
        const canvas = document.createElement('canvas');
        canvas.width = 200;
        canvas.height = 200;
        const ctx = canvas.getContext('2d');

        // Random background color
        const colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe'];
        const color = colors[Math.floor(Math.random() * colors.length)];

        ctx.fillStyle = color;
        ctx.fillRect(0, 0, 200, 200);

        // Add initials
        ctx.fillStyle = 'white';
        ctx.font = 'bold 80px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const initials = name ? name.substring(0, 2).toUpperCase() : '?';
        ctx.fillText(initials, 100, 100);

        currentAvatarData = canvas.toDataURL('image/png');
        displayAvatar(currentAvatarData);
    } catch (error) {
        console.error('Error generating avatar:', error);
        alert('Error generating avatar: ' + error.message);
    }
}

function displayAvatar(dataUrl) {
    const preview = document.getElementById('avatarPreview');
    preview.innerHTML = `<img src="${dataUrl}" style="width: 100%; height: 100%; object-fit: cover;">`;
}

async function loadAvatar(profileName) {
    try {
        const response = await CONFIG.fetch(`/api/profiles/${encodeURIComponent(profileName)}/avatar`);

        if (response.ok) {
            const data = await response.json();

            if (data.avatar) {
                // Check if it's a file path (new format) or base64 data URI (old format)
                if (data.avatar.startsWith('/uploads/')) {
                    // New format: construct full URL for display
                    const avatarUrl = `${CONFIG.API_BASE}${data.avatar}`;
                    currentAvatarData = data.avatar; // Store the path
                    displayAvatar(avatarUrl);
                } else if (data.avatar.startsWith('data:image/')) {
                    // Old format: base64 data URI
                    currentAvatarData = data.avatar;
                    displayAvatar(currentAvatarData);
                } else {
                    clearAvatar();
                }
            } else {
                clearAvatar();
            }
        } else {
            clearAvatar();
        }
    } catch (error) {
        console.error('[Avatar] Error loading avatar:', error);
        clearAvatar();
    }
}

async function saveAvatar(profileName) {
    if (!currentAvatarData) return;

    try {
        // Check if it's a File object (new format) or base64 string (generated avatar)
        if (currentAvatarData instanceof File) {
            // Send as FormData for file upload
            const formData = new FormData();
            formData.append('avatar', currentAvatarData);

            const response = await fetch(`${CONFIG.API_BASE}/api/profiles/${encodeURIComponent(profileName)}/avatar`, {
                method: 'POST',
                headers: {
                    'X-API-Key': CONFIG.API_KEY
                },
                body: formData
            });

            if (!response.ok) {
                console.error('Failed to save avatar');
            }
        } else if (typeof currentAvatarData === 'string') {
            // For generated avatars (base64), convert to Blob and upload
            const response = await fetch(currentAvatarData);
            const blob = await response.blob();
            const file = new File([blob], 'avatar.png', { type: 'image/png' });

            const formData = new FormData();
            formData.append('avatar', file);

            const uploadResponse = await fetch(`${CONFIG.API_BASE}/api/profiles/${encodeURIComponent(profileName)}/avatar`, {
                method: 'POST',
                headers: {
                    'X-API-Key': CONFIG.API_KEY
                },
                body: formData
            });

            if (!uploadResponse.ok) {
                console.error('Failed to save avatar');
            }
        }
    } catch (error) {
        console.error('Error saving avatar:', error);
    }
}

function clearAvatar() {
    currentAvatarData = null;
    const preview = document.getElementById('avatarPreview');
    preview.innerHTML = '<span style="color: #999;">No Avatar</span>';
}

// Major Life Events Management
function loadMajorLifeEvents(events) {
    const container = document.getElementById('majorLifeEventsList');
    container.innerHTML = '';

    if (!events || events.length === 0) {
        return;
    }

    events.forEach((event, index) => {
        addLifeEventToDOM(event, index);
    });
}

function addLifeEvent() {
    const container = document.getElementById('majorLifeEventsList');
    const index = container.children.length;
    addLifeEventToDOM('', index);
}

function addLifeEventToDOM(eventText, index) {
    const container = document.getElementById('majorLifeEventsList');

    const eventDiv = document.createElement('div');
    eventDiv.className = 'life-event-item';
    eventDiv.style.cssText = 'display: flex; gap: 10px; margin-bottom: 10px; align-items: center;';

    const input = document.createElement('input');
    input.type = 'text';
    input.value = eventText;
    input.placeholder = 'e.g., Graduated college in 2015';
    input.style.cssText = 'flex: 1;';
    input.className = 'life-event-input';
    input.maxLength = 150;

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.textContent = '✕';
    removeBtn.className = 'btn-delete';
    removeBtn.style.cssText = 'padding: 5px 10px; min-width: auto;';
    removeBtn.onclick = function() {
        eventDiv.remove();
    };

    eventDiv.appendChild(input);
    eventDiv.appendChild(removeBtn);
    container.appendChild(eventDiv);
}

function getMajorLifeEvents() {
    const inputs = document.querySelectorAll('.life-event-input');
    const events = [];

    inputs.forEach(input => {
        const value = input.value.trim();
        if (value) {
            events.push(value);
        }
    });

    return events;
}

// Shared Roleplay Events Management
// Roleplay events functions removed - using conversation history instead

// ============================================================================
// CONSENT MANAGEMENT
// ============================================================================

async function checkConsentStatus() {
    try {
        const response = await CONFIG.fetch('/api/consent');
        if (response.ok) {
            const data = await response.json();

            if (data.accepted) {
                // Consent already given - hide consent form, show regular form
                document.getElementById('consentSection').style.display = 'none';
                document.getElementById('profileForm').style.display = 'block';
            } else {
                // Need consent - show consent form, hide regular form
                document.getElementById('consentSection').style.display = 'block';
                document.getElementById('profileForm').style.display = 'none';
                setupConsentHandlers();
            }
        } else {
            // Default to showing consent form if can't load status
            document.getElementById('consentSection').style.display = 'block';
            document.getElementById('profileForm').style.display = 'none';
            setupConsentHandlers();
        }
    } catch (error) {
        console.error('Error checking consent status:', error);
        // Default to showing consent form
        document.getElementById('consentSection').style.display = 'block';
        document.getElementById('profileForm').style.display = 'none';
        setupConsentHandlers();
    }
}

function setupConsentHandlers() {
    // Setup checkbox change handlers
    const checkboxes = [
        'consentAge',
        'consentFictionality',
        'consentProhibited',
        'consentRealPerson',
        'consentHallucinations',
        'consentNarrativeConsent',
        'consentExperimental',
        'consentTerms'
    ];

    checkboxes.forEach(id => {
        const checkbox = document.getElementById(id);
        if (checkbox) {
            checkbox.addEventListener('change', updateConsentButton);
        }
    });

    // Setup button handler
    const acceptBtn = document.getElementById('acceptConsentBtn');
    if (acceptBtn) {
        acceptBtn.addEventListener('click', acceptConsent);
    }

    // Setup terms link handler
    const termsLink = document.getElementById('viewTermsLink');
    if (termsLink) {
        termsLink.addEventListener('click', (e) => {
            e.preventDefault();
            showTermsModal();
        });
    }

    // Setup close modal button
    const closeBtn = document.getElementById('closeTermsBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', hideTermsModal);
    }
}

function updateConsentButton() {
    const allChecked =
        document.getElementById('consentAge').checked &&
        document.getElementById('consentFictionality').checked &&
        document.getElementById('consentProhibited').checked &&
        document.getElementById('consentRealPerson').checked &&
        document.getElementById('consentHallucinations').checked &&
        document.getElementById('consentNarrativeConsent').checked &&
        document.getElementById('consentExperimental').checked &&
        document.getElementById('consentTerms').checked;

    const acceptBtn = document.getElementById('acceptConsentBtn');
    const errorMsg = document.getElementById('consentError');

    if (allChecked) {
        acceptBtn.disabled = false;
        errorMsg.style.display = 'none';
    } else {
        acceptBtn.disabled = true;
    }
}

async function acceptConsent() {
    const allChecked =
        document.getElementById('consentAge').checked &&
        document.getElementById('consentFictionality').checked &&
        document.getElementById('consentProhibited').checked &&
        document.getElementById('consentRealPerson').checked &&
        document.getElementById('consentHallucinations').checked &&
        document.getElementById('consentNarrativeConsent').checked &&
        document.getElementById('consentExperimental').checked &&
        document.getElementById('consentTerms').checked;

    if (!allChecked) {
        const errorMsg = document.getElementById('consentError');
        errorMsg.style.display = 'block';
        return;
    }

    const consentData = {
        accepted: true,
        timestamp: new Date().toISOString(),
        version: '1.0',
        checkboxes: {
            ageConfirmation: document.getElementById('consentAge').checked,
            fictionalityAcknowledgment: document.getElementById('consentFictionality').checked,
            prohibitedActivities: document.getElementById('consentProhibited').checked,
            realPersonLikeness: document.getElementById('consentRealPerson').checked,
            aiLimitations: document.getElementById('consentHallucinations').checked,
            narrativeConsent: document.getElementById('consentNarrativeConsent').checked,
            experimentalRisks: document.getElementById('consentExperimental').checked,
            termsOfService: document.getElementById('consentTerms').checked
        }
    };

    try {
        const response = await CONFIG.fetch('/api/consent', {
            method: 'POST',
            body: JSON.stringify(consentData)
        });

        if (!response.ok) throw new Error('Failed to save consent');

        // Hide consent form, show regular form
        document.getElementById('consentSection').style.display = 'none';
        document.getElementById('profileForm').style.display = 'block';

        alert('Thank you for accepting the terms. You may now use the application.');
    } catch (error) {
        console.error('Error saving consent:', error);
        alert('Error saving consent: ' + error.message);
    }
}

async function showTermsModal() {
    const modal = document.getElementById('termsModal');
    const content = document.getElementById('termsContent');

    modal.style.display = 'block';
    content.textContent = 'Loading...';

    try {
        const response = await fetch('/data/TERMS_OF_SERVICE.txt');
        if (response.ok) {
            const text = await response.text();
            content.textContent = text;
        } else {
            content.textContent = 'Error loading Terms of Service. Please check the file exists.';
        }
    } catch (error) {
        console.error('Error loading terms:', error);
        content.textContent = 'Error loading Terms of Service: ' + error.message;
    }
}

function hideTermsModal() {
    const modal = document.getElementById('termsModal');
    modal.style.display = 'none';
}

// ============================================================================
// CONVERSATION HISTORY MANAGEMENT
// ============================================================================

async function deleteAllConversations() {
    const confirmMessage = 'Are you sure you want to delete ALL conversation history?\n\n' +
        'This will permanently delete:\n' +
        '- All conversations with all characters\n' +
        '- All stored memories\n\n' +
        'This action CANNOT be undone!';

    if (!confirm(confirmMessage)) {
        return;
    }

    // Double confirmation for destructive action
    const doubleConfirm = confirm('This is your final warning. Click OK to permanently delete all conversation history.');

    if (!doubleConfirm) {
        return;
    }

    try {
        const response = await CONFIG.fetch('/api/conversations/delete-all', {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to delete conversations');
        }

        const result = await response.json();
        alert('Success! All conversation history has been permanently deleted.\n\n' +
              'Deleted: ' + (result.deleted_count || 0) + ' conversation records');

    } catch (error) {
        console.error('Error deleting conversations:', error);
        alert('Error deleting conversations: ' + error.message);
    }
}

async function deleteCharacterConversations(characterName) {
    const confirmMessage = `Are you sure you want to delete ALL conversation history with "${characterName}"?\n\n` +
        'This will permanently delete:\n' +
        `- All messages exchanged with ${characterName}\n` +
        `- All stored memories for ${characterName}\n\n` +
        'This action CANNOT be undone!';

    if (!confirm(confirmMessage)) {
        return;
    }

    try {
        const response = await CONFIG.fetch(`/api/conversations/delete-character/${encodeURIComponent(characterName)}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Failed to delete character conversations');
        }

        const result = await response.json();
        alert(`Success! Conversation history with "${characterName}" has been permanently deleted.\n\n` +
              'Deleted: ' + (result.deleted_count || 0) + ' conversation records');

    } catch (error) {
        console.error('Error deleting character conversations:', error);
        alert('Error deleting character conversations: ' + error.message);
    }
}

// Password change functionality
async function changePassword() {
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const statusDiv = document.getElementById('passwordChangeStatus');
    const changeBtn = document.getElementById('changePasswordBtn');

    // Clear previous status
    statusDiv.style.display = 'none';
    statusDiv.textContent = '';

    // Validate inputs
    if (!newPassword || !confirmPassword) {
        statusDiv.textContent = 'Please fill in both password fields';
        statusDiv.style.display = 'block';
        statusDiv.style.color = '#ff6b6b';
        return;
    }

    if (newPassword !== confirmPassword) {
        statusDiv.textContent = 'Passwords do not match';
        statusDiv.style.display = 'block';
        statusDiv.style.color = '#ff6b6b';
        return;
    }

    if (newPassword.length < 4) {
        statusDiv.textContent = 'Password must be at least 4 characters long';
        statusDiv.style.display = 'block';
        statusDiv.style.color = '#ff6b6b';
        return;
    }

    try {
        // Disable button during request
        changeBtn.disabled = true;
        changeBtn.textContent = 'Updating...';

        const response = await CONFIG.fetch('/auth/change-password', {
            method: 'POST',
            body: JSON.stringify({
                newPassword,
                confirmPassword
            })
        });

        const data = await response.json();

        if (data.success) {
            statusDiv.textContent = 'Password updated successfully!';
            statusDiv.style.display = 'block';
            statusDiv.style.color = '#1bafae';

            // Clear the password fields
            document.getElementById('newPassword').value = '';
            document.getElementById('confirmPassword').value = '';

            // Hide success message after 3 seconds
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, 3000);
        } else {
            statusDiv.textContent = data.error || 'Failed to update password';
            statusDiv.style.display = 'block';
            statusDiv.style.color = '#ff6b6b';
        }
    } catch (error) {
        console.error('Password change error:', error);
        statusDiv.textContent = 'Error updating password. Please try again.';
        statusDiv.style.display = 'block';
        statusDiv.style.color = '#ff6b6b';
    } finally {
        // Re-enable button
        changeBtn.disabled = false;
        changeBtn.textContent = 'Update Password';
    }
}

// Logout functionality
document.addEventListener('DOMContentLoaded', () => {
    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) {
        logoutButton.addEventListener('click', () => {
            // Use the auth helper to logout
            if (window.authHelpers && window.authHelpers.handleLogout) {
                window.authHelpers.handleLogout();
            } else {
                // Fallback if auth.js didn't load
                window.location.href = '/login';
            }
        });
    }
});

// ============================================================================
// TAG-BASED BEHAVIOR CONFIGURATION
// ============================================================================

function initializeTagButtons() {
    // Get all tag buttons
    const tagButtons = document.querySelectorAll('.tag-btn');

    // Add click handlers to all tag buttons
    tagButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            toggleTagSelection(this);
        });
    });
}

function toggleTagSelection(button) {
    const container = button.closest('.tag-options');
    const isSingleSelect = container.getAttribute('data-single-select') === 'true';

    if (isSingleSelect) {
        // Radio button behavior: deselect all others in this category, select this one
        const allButtonsInCategory = container.querySelectorAll('.tag-btn');
        allButtonsInCategory.forEach(btn => btn.classList.remove('selected'));
        button.classList.add('selected');
    } else {
        // Checkbox behavior: toggle this button
        button.classList.toggle('selected');
    }
}

function getSelectedTags() {
    // Get all tag-options containers
    const tagContainers = document.querySelectorAll('.tag-options');
    const tagSelections = {};

    tagContainers.forEach(container => {
        const category = container.getAttribute('data-category');
        const selectedButtons = container.querySelectorAll('.tag-btn.selected');

        // Only add category if it has selected tags
        if (selectedButtons.length > 0) {
            tagSelections[category] = Array.from(selectedButtons).map(btn =>
                btn.getAttribute('data-tag')
            );
        }
    });

    return tagSelections;
}

function loadTagSelections(tagSelections) {
    // First, clear all selections
    clearTagSelections();

    // Then set the loaded selections
    if (!tagSelections) return;

    Object.entries(tagSelections).forEach(([category, tags]) => {
        // Find the container for this category
        const container = Array.from(document.querySelectorAll('.tag-options'))
            .find(el => el.getAttribute('data-category') === category);

        if (!container) return;

        // Select each tag in this category
        tags.forEach(tagName => {
            const button = container.querySelector(`[data-tag="${tagName}"]`);
            if (button) {
                button.classList.add('selected');
            }
        });
    });
}

function clearTagSelections() {
    // Remove 'selected' class from all tag buttons
    const allTagButtons = document.querySelectorAll('.tag-btn');
    allTagButtons.forEach(button => {
        button.classList.remove('selected');
    });
}

// ============================================================================
// DATA IMPORT/EXPORT
// ============================================================================

async function exportData() {
    try {
        console.log('Exporting data...');

        const response = await fetch(`${API_BASE}/api/export-data`, {
            method: 'GET',
            credentials: 'include'
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
            console.error('Export failed:', errorData);
            throw new Error(errorData.message || 'Failed to export data');
        }

        const data = await response.json();

        // Create a download link with timestamp
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `echo-backup-${timestamp}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        console.log('Backup created successfully!');
        alert('✅ Backup downloaded successfully!\n\nFile: echo-backup-' + timestamp + '.json\n\nStore this file safely - it contains all your encrypted profile data.');
    } catch (error) {
        console.error('Export error:', error);
        alert('Failed to export data: ' + error.message);
    }
}

// Import functionality removed for security - users should restore from encrypted backups manually