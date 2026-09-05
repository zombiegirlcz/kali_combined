# Implementation Plan: Kali AI Assistant Enhancements

## Overview
This plan addresses the requested features to enhance the Kali AI Assistant monorepo with better model selection, provider management, GitHub integration, workspace management, and plan modes.

## Current State Analysis

### Existing Features ( ✅ )
1. **Model Selection**: Basic provider/model selection in SettingsScreen.kt
2. **Favorites**: Basic model favorites system in SecureKeyStore.kt
3. **GitHub Authentication**: Device flow OAuth implementation in GitHubAuth.kt
4. **Provider Management**: OpenAI-compatible provider configs with Base URL support
5. **Model Fetching**: Real-time model fetching from providers via ModelRegistry.kt

### Gaps ( ❌ )
1. **Model Overview Window**: No comprehensive model selection UI
2. **Provider Categories**: No categorization of providers by type (OpenAI, Anthropic, etc.)
3. **Enhanced GitHub Flow**: Manual clipboard copy, no automatic flow
4. **Workspace Management**: No rootfs folder structure for repos
5. **Plan Modes**: No auto-accept yolo mode or colored themes
6. **Search Functionality**: No search in model/provider selection

## Feature Implementation Plan

### Phase 1: Enhanced Model Selection (Week 1-2)

#### 1.1 Comprehensive Model Overview Component
**Location**: `app/src/main/java/com/kali/aiassistant/ui/chat/ModelOverviewScreen.kt`

**Features**:
- Centralized model selection UI with provider categorization
- Search functionality (model name, provider, tags)
- Provider type filtering (OpenAI, Anthropic, Google, Custom)
- Favorites quick access
- Model details panel (context window, pricing, capabilities)
- Compare mode for multiple models side-by-side

**Data Structure**:
```kotlin
data class ModelInfo(
    val id: String,
    val name: String,
    val providerId: String,
    val providerName: String,
    val source: ModelSource,
    val contextWindow: Int?,
    val maxOutputTokens: Int?,
    val priceInput: Double?,
    val priceOutput: Double?,
    val supportsVision: Boolean,
    val supportsTools: Boolean,
    val modalities: List<String>,
    val isFavorite: Boolean,
    val tags: List<String>,
    val category: ProviderCategory
)

enum class ProviderCategory {
    OPENAI, ANTHROPIC, GOOGLE, OPENROUTER, GROQ, KILOCODE, OPENCODE, OLLAMA, CUSTOM
}
```

#### 1.2 Provider Categorization System
**Location**: `app/src/main/java/com/kali/aiassistant/data/api/ProviderRegistry.kt`

**Features**:
- Automatic provider type detection based on base URL and capabilities
- Default provider categories pre-configured
- Custom category support
- Category-based filtering in UI

### Phase 2: Enhanced GitHub Integration (Week 2-3)

#### 2.1 Automatic GitHub Login Flow
**Location**: `app/src/main/java/com/kali/aiassistant/ui/chat/GitHubLoginFlow.kt`

**Features**:
- Automatic clipboard save of user code
- Web view for verification URL opening
- Real-time polling status
- Success/failure notifications
- Fallback options

**Implementation Flow**:
1. Request device code
2. Auto-copy user code to clipboard
3. Open verification URL in browser
4. Poll for token completion
5. Auto-store token and user info

#### 2.2 Repository Management Window
**Location**: `app/src/main/java/com/kali/aiassistant/ui/chat/RepositoryManager.kt`

**Features**:
- Separate repo list window
- Repository details (size, last updated, description)
- Clone options (depth, branch selection)
- Workspace assignment
- Bulk operations

#### 2.3 Workspace Management System
**Location**: `app/src/main/java/com/kali/aiassistant/data/workspace/WorkspaceManager.kt`

**Features**:
- Rootfs folder structure for repos
- Workspace selection UI
- Persistent workspace configuration
- Git remote management
- Project linking to workspaces

### Phase 3: Workspace and Workspace Features (Week 3-4)

#### 3.1 Rootfs Workspace Structure
**Directory Structure**:
```
/rootfs/
├── workspaces/
│   ├── gh_{repo_name}/ (cloned repos)
│   ├── local_/ (user-selected workspaces)
│   └── temp_/ (temporary workspaces)
├── cache/ (model cache)
├── configs/ (provider configurations)
└── logs/ (application logs)
```

**Implementation**:
```kotlin
class WorkspaceManager {
    fun getWorkspacePath(workspaceId: String): String
    fun listWorkspaces(): List<WorkspaceInfo>
    fun createWorkspace(name: String, type: WorkspaceType): String
    fun selectWorkspace(workspaceId: String): Boolean
    fun getActiveWorkspace(): WorkspaceInfo?
}
```

#### 3.2 Enhanced Plan Modes
**Location**: `app/src/main/java/com/kali/aiassistant/data/PlanMode.kt`

**Features**:
- **YOLO Mode**: Auto-accept all changes, skip confirmations
- **Auto-Accept Mode**: Auto-apply suggestions
- **Colored Theme System**: Dark/Light/High-contrast themes
- **Plan Mode Switcher**: Quick mode toggling

**UI Component**:
```kotlin
@Composable
fun PlanModeSelector(
    currentMode: PlanMode,
    onModeChange: (PlanMode) -> Unit
) {
    Row {
        ModeChip(PlanMode.YOLO, "YOLO", Color.Red)
        ModeChip(PlanMode.AUTO_ACCEPT, "Auto-Accept", Color.Green)
        ModeChip(PlanMode.MANUAL, "Manual", Color.Blue)
        ModeChip(PlanMode.DARK, "Dark", Color.DarkGray)
        ModeChip(PlanMode.LIGHT, "Light", Color.LightGray)
    }
}
```

### Phase 4: Integration and Polish (Week 4)

#### 4.1 Unified Model Selector
**Location**: Replace SettingsScreen.kt Provider section with ModelOverviewScreen.kt

#### 4.2 GitHub Integration Polish
- Smooth transitions between GitHub login and repo selection
- Loading states and error handling
- Offline capabilities

#### 4.3 Workspace Integration
- Auto-detect existing repos in workspaces
- Smart workspace suggestions based on usage patterns
- Backup and sync options

### Phase 5: Testing and Deployment (Week 5)

#### 5.1 Comprehensive Testing
```kotlin
// Test cases for new features
testModelSearch()
testProviderCategorization()
testGitHubAutoLogin()
testWorkspaceManagement()
testPlanModes()
```

#### 5.2 UI/UX Testing
- Accessibility compliance
- Performance optimization
- Cross-device compatibility

## Technical Implementation Details

### Architecture Decisions

1. **State Management**: Use MVVM with StateFlow for reactive UI
2. **Navigation**: Jetpack Compose Navigation with deep linking
3. **Async Operations**: Coroutines with proper error handling
4. **Persistence**: SecureKeyStore for sensitive data

### Code Organization

```
app/src/main/java/com/kali/aiassistant/
├── ui/
│   ├── chat/ (ChatScreen, ModelOverviewScreen, GitHubLoginFlow, RepositoryManager)
│   ├── settings/ (SettingsScreen)
│   └── theme/ (PlanModeSelector)
├── data/
│   ├── api/ (ProviderRegistry, WorkspaceManager, PlanMode)
│   ├── prefs/ (WorkspacePreferences)
│   └── workspace/ (WorkspaceManager)
├── domain/ (ModelInfo, ProviderConfig, WorkspaceConfig)
└── agent/ (Tool integration)
```

### Performance Considerations

1. **Lazy Loading**: Load models/providers on demand
2. **Caching**: Cache model lists and workspace info
3. **Debounced Search**: Debounce search queries for better performance
4. **Memory Management**: Proper cleanup of temporary workspaces

### Security Considerations

1. **GitHub Tokens**: Secure storage in KeyStore
2. **Workspace Access**: Permission-based access control
3. **Plan Mode Safety**: Safeguards in YOLO mode
4. **Data Validation**: Input validation for all user-provided data

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| GitHub API changes | Medium | Medium | Version detection and fallbacks |
| Performance issues | Low | High | Performance testing, optimization |
| UI complexity | Medium | Medium | Progressive rollout, user testing |
| Security vulnerabilities | Low | Critical | Security reviews, penetration testing |

## Timeline

- **Week 1-2**: Enhanced Model Selection
- **Week 3**: GitHub Integration
- **Week 4**: Workspace and Plan Modes
- **Week 5**: Integration and Testing

Total: 5 weeks (40 working days)

## Success Criteria

1. **Model Selection**: 90% reduction in provider switching time
2. **GitHub Flow**: 100% auto-login success rate
3. **Workspace Management**: <100ms workspace access time
4. **Plan Modes**: User satisfaction score >4/5
5. **Overall**: No regression in existing functionality

## Dependencies

```gradle
dependencies {
    // UI components
    implementation "androidx.compose.material3:material3:1.2.0"
    implementation "androidx.navigation:navigation-compose:2.7.5"
    
    // Security
    implementation "androidx.security:security-crypto:1.1.0-alpha06"
    
    // Networking
    implementation "com.squareup.okhttp3:okhttp:4.12.0"
    implementation "com.squareup.retrofit2:retrofit:2.9.0"
    
    // Data
    implementation "org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3"
}
```

## Next Steps

1. Start implementation of Phase 1 (Enhanced Model Selection)
2. Set up project structure and modularization
3. Create test suite for new features
4. Begin development with iterative approach
5. Regular integration testing and user feedback collection

This plan provides a comprehensive roadmap for implementing all requested features while maintaining code quality, security, and performance standards.