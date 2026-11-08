; Game Mode Installer - Multi-language (EN/PT/ES) with Theme Support
; Supports: English (default), Portuguese (Brazil), Spanish
; Theme: Light/Dark/System

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "WinMessages.nsh"

; ============================================================================
; BASIC SETTINGS
; ============================================================================
Name "Game Mode"
OutFile "Instalar_GameMode_${APP_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\GameMode"
InstallDirRegKey HKCU "Software\GameMode" "InstallDir"
RequestExecutionLevel user
ShowInstDetails show

; Version
!define APP_VERSION "2.5.0"
!define APP_NAME "Game Mode"
!define APP_PUBLISHER "RegenKaboom"
!define APP_URL "https://github.com/RegenKaboom/gamemode"
!define APP_CONTACT "https://github.com/RegenKaboom/gamemode/issues"

; ============================================================================
; LANGUAGE SUPPORT
; ============================================================================
; English (default)
!insertmacro MUI_LANGUAGE "English"
LangString LANG_ENGLISH ${LANG_ENGLISH} "English"
LangString LANG_PORTUGUESE ${LANG_ENGLISH} "Português (Brasil)"
LangString LANG_SPANISH ${LANG_ENGLISH} "Español"

; Portuguese (Brazil)
!insertmacro MUI_LANGUAGE "PortugueseBR"
LangString LANG_ENGLISH ${LANG_PORTUGUESE} "English"
LangString LANG_PORTUGUESE ${LANG_PORTUGUESE} "Português (Brasil)"
LangString LANG_SPANISH ${LANG_PORTUGUESE} "Español"

; Spanish
!insertmacro MUI_LANGUAGE "Spanish"
LangString LANG_ENGLISH ${LANG_SPANISH} "English"
LangString LANG_PORTUGUESE ${LANG_SPANISH} "Português (Brasil)"
LangString LANG_SPANISH ${LANG_SPANISH} "Español"

; ============================================================================
; MULTILINGUAL STRINGS
; ============================================================================
; English strings
LangString STR_WELCOME ${LANG_ENGLISH} "Welcome to the Game Mode Setup Wizard"
LangString STR_WELCOME_INFO ${LANG_ENGLISH} "This wizard will guide you through the installation of Game Mode.\n\nClick Next to continue."
LangString STR_LICENSE ${LANG_ENGLISH} "License Agreement"
LangString STR_LICENSE_INFO ${LANG_ENGLISH} "Please read the license agreement before installing."
LangString STR_COMPONENTS ${LANG_ENGLISH} "Choose Components"
LangString STR_COMPONENTS_INFO ${LANG_ENGLISH} "Select the features you want to install:"
LangString STR_DESTINATION ${LANG_ENGLISH} "Destination Folder"
LangString STR_DESTINATION_INFO ${LANG_ENGLISH} "Choose the installation folder."
LangString STR_LANGUAGE ${LANG_ENGLISH} "Select Language"
LangString STR_LANGUAGE_INFO ${LANG_ENGLISH} "Choose the language for the installer and application."
LangString STR_THEME ${LANG_ENGLISH} "Select Theme"
LangString STR_THEME_INFO ${LANG_ENGLISH} "Choose the visual theme for the application."
LangString STR_SHORTCUTS ${LANG_ENGLISH} "Create Shortcuts"
LangString STR_SHORTCUTS_INFO ${LANG_ENGLISH} "Choose where to create shortcuts."
LangString STR_INSTALLING ${LANG_ENGLISH} "Installing Game Mode..."
LangString STR_FINISHED ${LANG_ENGLISH} "Installation Complete"
LangString STR_FINISHED_INFO ${LANG_ENGLISH} "Game Mode has been installed successfully."
LangString STR_LAUNCH ${LANG_ENGLISH} "Launch Game Mode"
LangString STR_UNINSTALL ${LANG_ENGLISH} "Uninstall Game Mode"
LangString STR_UNINSTALL_CONFIRM ${LANG_ENGLISH} "Are you sure you want to uninstall Game Mode?"
LangString STR_REMOVE_CONFIGS ${LANG_ENGLISH} "Remove configuration files and settings"
LangString STR_COMPONENT_CORE ${LANG_ENGLISH} "Core Optimizer (required)"
LangString STR_COMPONENT_OVERLAY ${LANG_ENGLISH} "HUD Overlay"
LangString STR_COMPONENT_FNF ${LANG_ENGLISH} "FNF Mode (4 lanes)"
LangString STR_COMPONENT_SOCD ${LANG_ENGLISH} "SOCD Cleaner"
LangString STR_COMPONENT_EXTRAS ${LANG_ENGLISH} "Extra Tools (cleanup, playtime, etc.)"
LangString STR_COMPONENT_STARTUP ${LANG_ENGLISH} "Start with Windows"
LangString STR_THEME_LIGHT ${LANG_ENGLISH} "Light"
LangString STR_THEME_DARK ${LANG_ENGLISH} "Dark"
LangString STR_THEME_SYSTEM ${LANG_ENGLISH} "System Default"
LangString STR_DETECTING ${LANG_ENGLISH} "Detecting games..."

; Portuguese strings
LangString STR_WELCOME ${LANG_PORTUGUESE} "Bem-vindo ao Assistente de Instalação do Game Mode"
LangString STR_WELCOME_INFO ${LANG_PORTUGUESE} "Este assistente irá guiá-lo na instalação do Game Mode.\n\nClique em Avançar para continuar."
LangString STR_LICENSE ${LANG_PORTUGUESE} "Contrato de Licença"
LangString STR_LICENSE_INFO ${LANG_PORTUGUESE} "Leia o contrato de licença antes de instalar."
LangString STR_COMPONENTS ${LANG_PORTUGUESE} "Escolher Componentes"
LangString STR_COMPONENTS_INFO ${LANG_PORTUGUESE} "Selecione os recursos que deseja instalar:"
LangString STR_DESTINATION ${LANG_PORTUGUESE} "Pasta de Destino"
LangString STR_DESTINATION_INFO ${LANG_PORTUGUESE} "Escolha a pasta de instalação."
LangString STR_LANGUAGE ${LANG_PORTUGUESE} "Selecionar Idioma"
LangString STR_LANGUAGE_INFO ${LANG_PORTUGUESE} "Escolha o idioma do instalador e do aplicativo."
LangString STR_THEME ${LANG_PORTUGUESE} "Selecionar Tema"
LangString STR_THEME_INFO ${LANG_PORTUGUESE} "Escolha o tema visual do aplicativo."
LangString STR_SHORTCUTS ${LANG_PORTUGUESE} "Criar Atalhos"
LangString STR_SHORTCUTS_INFO ${LANG_PORTUGUESE} "Escolha onde criar atalhos."
LangString STR_INSTALLING ${LANG_PORTUGUESE} "Instalando Game Mode..."
LangString STR_FINISHED ${LANG_PORTUGUESE} "Instalação Concluída"
LangString STR_FINISHED_INFO ${LANG_PORTUGUESE} "O Game Mode foi instalado com sucesso."
LangString STR_LAUNCH ${LANG_PORTUGUESE} "Iniciar Game Mode"
LangString STR_UNINSTALL ${LANG_PORTUGUESE} "Desinstalar Game Mode"
LangString STR_UNINSTALL_CONFIRM ${LANG_PORTUGUESE} "Tem certeza que deseja desinstalar o Game Mode?"
LangString STR_REMOVE_CONFIGS ${LANG_PORTUGUESE} "Remover arquivos de configuração e preferências"
LangString STR_COMPONENT_CORE ${LANG_PORTUGUESE} "Otimizador Principal (obrigatório)"
LangString STR_COMPONENT_OVERLAY ${LANG_PORTUGUESE} "Overlay HUD"
LangString STR_COMPONENT_FNF ${LANG_PORTUGUESE} "Modo FNF (4 pistas)"
LangString STR_COMPONENT_SOCD ${LANG_PORTUGUESE} "SOCD Cleaner"
LangString STR_COMPONENT_EXTRAS ${LANG_PORTUGUESE} "Ferramentas Extras (limpeza, tempo de jogo, etc.)"
LangString STR_COMPONENT_STARTUP ${LANG_PORTUGUESE} "Iniciar com o Windows"
LangString STR_THEME_LIGHT ${LANG_PORTUGUESE} "Claro"
LangString STR_THEME_DARK ${LANG_PORTUGUESE} "Escuro"
LangString STR_THEME_SYSTEM ${LANG_PORTUGUESE} "Padrão do Sistema"
LangString STR_DETECTING ${LANG_PORTUGUESE} "Detectando jogos..."

; Spanish strings
LangString STR_WELCOME ${LANG_SPANISH} "Bienvenido al Asistente de Instalación de Game Mode"
LangString STR_WELCOME_INFO ${LANG_SPANISH} "Este asistente le guiará en la instalación de Game Mode.\n\nHaga clic en Siguiente para continuar."
LangString STR_LICENSE ${LANG_SPANISH} "Contrato de Licencia"
LangString STR_LICENSE_INFO ${LANG_SPANISH} "Lea el contrato de licencia antes de instalar."
LangString STR_COMPONENTS ${LANG_SPANISH} "Elegir Componentes"
LangString STR_COMPONENTS_INFO ${LANG_SPANISH} "Seleccione las características que desea instalar:"
LangString STR_DESTINATION ${LANG_SPANISH} "Carpeta de Destino"
LangString STR_DESTINATION_INFO ${LANG_SPANISH} "Elija la carpeta de instalación."
LangString STR_LANGUAGE ${LANG_SPANISH} "Seleccionar Idioma"
LangString STR_LANGUAGE_INFO ${LANG_SPANISH} "Elija el idioma del instalador y la aplicación."
LangString STR_THEME ${LANG_SPANISH} "Seleccionar Tema"
LangString STR_THEME_INFO ${LANG_SPANISH} "Elija el tema visual de la aplicación."
LangString STR_SHORTCUTS ${LANG_SPANISH} "Crear Accesos Directos"
LangString STR_SHORTCUTS_INFO ${LANG_SPANISH} "Elija dónde crear accesos directos."
LangString STR_INSTALLING ${LANG_SPANISH} "Instalando Game Mode..."
LangString STR_FINISHED ${LANG_SPANISH} "Instalación Completada"
LangString STR_FINISHED_INFO ${LANG_SPANISH} "Game Mode se ha instalado correctamente."
LangString STR_LAUNCH ${LANG_SPANISH} "Iniciar Game Mode"
LangString STR_UNINSTALL ${LANG_SPANISH} "Desinstalar Game Mode"
LangString STR_UNINSTALL_CONFIRM ${LANG_SPANISH} "¿Seguro que quieres desinstalar Game Mode?"
LangString STR_REMOVE_CONFIGS ${LANG_SPANISH} "Eliminar archivos de configuración y preferencias"
LangString STR_COMPONENT_CORE ${LANG_SPANISH} "Optimizador Principal (obligatorio)"
LangString STR_COMPONENT_OVERLAY ${LANG_SPANISH} "Overlay HUD"
LangString STR_COMPONENT_FNF ${LANG_SPANISH} "Modo FNF (4 carriles)"
LangString STR_COMPONENT_SOCD ${LANG_SPANISH} "SOCD Cleaner"
LangString STR_COMPONENT_EXTRAS ${LANG_SPANISH} "Herramientas Extras (limpieza, tiempo de juego, etc.)"
LangString STR_COMPONENT_STARTUP ${LANG_SPANISH} "Iniciar con Windows"
LangString STR_THEME_LIGHT ${LANG_SPANISH} "Claro"
LangString STR_THEME_DARK ${LANG_SPANISH} "Oscuro"
LangString STR_THEME_SYSTEM ${LANG_SPANISH} "Predeterminado del Sistema"
LangString STR_DETECTING ${LANG_SPANISH} "Detectando juegos..."

; ============================================================================
; VARIABLES
; ============================================================================
Var SELECTED_LANG
Var SELECTED_THEME
Var INSTALL_CORE
Var INSTALL_OVERLAY
Var INSTALL_FNF
Var INSTALL_SOCD
Var INSTALL_EXTRAS
Var INSTALL_STARTUP
Var CONFIG_DIR

; ============================================================================
; CUSTOM PAGES
; ============================================================================
; Language selection page
!define MUI_CUSTOMFUNCTION_PRE_LANGUAGE_PAGE LanguagePagePre
!insertmacro MUI_PAGE_CUSTOM LanguagePageCreate LanguagePageLeave

; Theme selection page
!define MUI_CUSTOMFUNCTION_PRE_THEME_PAGE ThemePagePre
!insertmacro MUI_PAGE_CUSTOM ThemePageCreate ThemePageLeave

; ============================================================================
; MUI PAGES
; ============================================================================
!insertmacro MUI_PAGE_WELCOME
Page Custom LanguagePageCreate LanguagePageLeave
Page Custom ThemePageCreate ThemePageLeave
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_SHORTCUTS
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\GameMode.exe"
!define MUI_FINISHPAGE_RUN_TEXT "$(STR_LAUNCH)"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!define MUI_UNPAGE_INSTFILES_TEXT "Removing files..."
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; ============================================================================
; UI SETTINGS
; ============================================================================
!define MUI_ICON "app.ico"
!define MUI_UNICON "app.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "welcome.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "welcome.bmp"

; ============================================================================
; LANGUAGE PAGE
; ============================================================================
Function LanguagePageCreate
    !insertmacro MUI_HEADER_TEXT "$(STR_LANGUAGE)" "$(STR_LANGUAGE_INFO)"

    nsDialogs::Create 1018
    Pop $0

    ${NSD_CreateLabel} 0 0 100% 20u "Select installation language:"
    Pop $0

    ${NSD_CreateComboBox} 0 30u 100% 100u
    Pop $SELECTED_LANG

    ${NSD_CB_AddString} $SELECTED_LANG "$(LANG_ENGLISH)"
    ${NSD_CB_AddString} $SELECTED_LANG "$(LANG_PORTUGUESE)"
    ${NSD_CB_AddString} $SELECTED_LANG "$(LANG_SPANISH)"

    ${NSD_CB_SelectString} $SELECTED_LANG "$(LANG_ENGLISH)"

    nsDialogs::Show
FunctionEnd

Function LanguagePageLeave
    ${NSD_CB_GetText} $SELECTED_LANG $0
    StrCpy $SELECTED_LANG $0
FunctionEnd

Function LanguagePagePre
    ; Set MUI language based on selection
    ${NSD_CB_GetText} $SELECTED_LANG $0
    StrCmp $0 "$(LANG_PORTUGUESE)" 0 +2
        MUI_LANGDLL_DISPLAY LANG_PORTUGUESE
        Goto +2
    StrCmp $0 "$(LANG_SPANISH)" 0 +2
        MUI_LANGDLL_DISPLAY LANG_SPANISH
    ; Default English
FunctionEnd

; ============================================================================
; THEME PAGE
; ============================================================================
Function ThemePageCreate
    !insertmacro MUI_HEADER_TEXT "$(STR_THEME)" "$(STR_THEME_INFO)"

    nsDialogs::Create 1018
    Pop $0

    ${NSD_CreateLabel} 0 0 100% 20u "Select application theme:"
    Pop $0

    ${NSD_CreateRadioButton} 0 30u 100% 20u "$(STR_THEME_SYSTEM)"
    Pop $0
    ${NSD_CreateRadioButton} 0 55u 100% 20u "$(STR_THEME_LIGHT)"
    Pop $1
    ${NSD_CreateRadioButton} 0 80u 100% 20u "$(STR_THEME_DARK)"
    Pop $2

    ; Store handles
    StrCpy $SELECTED_THEME $0

    ; Default to system
    SendMessage $0 ${BM_SETCHECK} ${BST_CHECKED} 0

    nsDialogs::Show
FunctionEnd

Function ThemePageLeave
    ${NSD_GetState} $SELECTED_THEME $0
    ${NSD_GetState} $1 $1
    ${NSD_GetState} $2 $2

    StrCmp $0 ${BST_CHECKED} 0 +2
        StrCpy $SELECTED_THEME "system"
        Goto +2
    StrCmp $1 ${BST_CHECKED} 0 +2
        StrCpy $SELECTED_THEME "light"
        Goto +2
    StrCmp $2 ${BST_CHECKED} 0 +2
        StrCpy $SELECTED_THEME "dark"
FunctionEnd

Function ThemePagePre
    ; Nothing special needed
FunctionEnd

; ============================================================================
; INSTALLER SECTIONS
; ============================================================================
Section "Core" SEC_CORE
    SectionIn RO
    SetOutPath "$INSTDIR"
    File "build\gamemode_app.dist\GameMode.exe"
    File "app.ico"

    ; Create config directory
    StrCpy $CONFIG_DIR "$APPDATA\GameModeLite"
    CreateDirectory "$CONFIG_DIR"

    ; Save language and theme preferences
    StrCpy $0 "$CONFIG_DIR\installer_config.json"
    FileOpen $1 $0 w
    FileWrite $1 '{"language": "$SELECTED_LANG", "theme": "$SELECTED_THEME"}' $\r$\n
    FileClose $1

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Registry entries
    WriteRegStr HKCU "Software\GameMode" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\GameMode" "Version" "${APP_VERSION}"
    WriteRegStr HKCU "Software\GameMode" "Language" "$SELECTED_LANG"
    WriteRegStr HKCU "Software\GameMode" "Theme" "$SELECTED_THEME"

    ; Uninstall registry
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GameMode" \
        "DisplayName" "$(APP_NAME)"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GameMode" \
        "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GameMode" \
        "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GameMode" \
        "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GameMode" \
        "URLInfoAbout" "${APP_URL}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GameMode" \
        "NoModify" "1"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GameMode" \
        "NoRepair" "1"

    ; Component flags
    StrCpy $INSTALL_CORE 1
SectionEnd

Section "Overlay" SEC_OVERLAY
    StrCpy $INSTALL_OVERLAY 1
SectionEnd

Section "FNF Mode" SEC_FNF
    StrCpy $INSTALL_FNF 1
SectionEnd

Section "SOCD Cleaner" SEC_SOCD
    StrCpy $INSTALL_SOCD 1
SectionEnd

Section "Extras" SEC_EXTRAS
    StrCpy $INSTALL_EXTRAS 1
SectionEnd

Section "Start with Windows" SEC_STARTUP
    StrCpy $INSTALL_STARTUP 1
SectionEnd

; ============================================================================
; INSTALLER CALLBACKS
; ============================================================================
Function .onInit
    ; Set default language to English
    StrCpy $SELECTED_LANG "$(LANG_ENGLISH)"
    StrCpy $SELECTED_THEME "system"

    ; Initialize component variables
    StrCpy $INSTALL_CORE 1
    StrCpy $INSTALL_OVERLAY 1
    StrCpy $INSTALL_FNF 0
    StrCpy $INSTALL_SOCD 0
    StrCpy $INSTALL_EXTRAS 1
    StrCpy $INSTALL_STARTUP 0
FunctionEnd

Function .onSelChange
    ; Handle component selection changes
    !insertmacro StartRadioButtons $SEC_CORE
        SectionGetFlags ${SEC_CORE} $0
        IntOp $0 $0 & ${SF_RO}
        IntCmp $0 ${SF_RO} 0 +2
            Abort
    !insertmacro EndRadioButtons
FunctionEnd

; ============================================================================
; UNINSTALLER
; ============================================================================
Section "Uninstall"
    ; Remove files
    RMDir /r "$INSTDIR"

    ; Ask to remove configs
    MessageBox MB_YESNO|MB_ICONQUESTION "$(STR_UNINSTALL_CONFIRM)" IDNO +2
        RMDir /r "$APPDATA\GameModeLite"

    ; Remove registry
    DeleteRegKey HKCU "Software\GameMode"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GameMode"

    ; Remove startup
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "GameMode"
SectionEnd

Function un.onInit
    ; Load language from registry
    ReadRegStr $0 HKCU "Software\GameMode" "Language"
    StrCmp $0 "" 0 +2
        StrCpy $SELECTED_LANG $0
    ; Language already set by MUI
FunctionEnd

; ============================================================================
; SILENT INSTALL SUPPORT
; ============================================================================
Function .onSilentInstall
    StrCpy $SELECTED_LANG "$(LANG_ENGLISH)"
    StrCpy $SELECTED_THEME "system"
    StrCpy $INSTALL_CORE 1
    StrCpy $INSTALL_OVERLAY 1
    StrCpy $INSTALL_FNF 0
    StrCpy $INSTALL_SOCD 0
    StrCpy $INSTALL_EXTRAS 1
    StrCpy $INSTALL_STARTUP 0
FunctionEnd