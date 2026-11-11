; Game Mode installer (compiled program: Python is NOT needed).
; The program must already be compiled into build\gamemode_app.dist (see COMPILAR.txt), then
; right-click this file > "Compile NSIS Script". Languages: English (default), Portuguese (BR), Spanish.

Unicode true
!define APP_NAME "Game Mode"
!ifndef APP_VERSION
  !define APP_VERSION "2.5"
!endif
!define APP_EXE "GameMode.exe"
!define DIST "build\gamemode_app.dist"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\GameMode"
!define RUN_KEY "Software\Microsoft\Windows\CurrentVersion\Run"
!define RUN_NAME "GameModeLite"
!define DATA_DIR "$APPDATA\GameModeLite"

!if /FileExists "${__FILEDIR__}\${DIST}\${APP_EXE}"
!else
  !error "The compiled program is missing in ${DIST}. Compile Game Mode first (see COMPILAR.txt)."
!endif

Name "${APP_NAME}"
OutFile "Instalar_GameMode_${APP_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\GameMode"
InstallDirRegKey HKCU "${UNINST_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "${APP_NAME} ${APP_VERSION}"

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"
!insertmacro GetSize

; ---------- look (black side panel, like the Steam installer)
!define MUI_ICON "app.ico"
!define MUI_UNICON "app.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "welcome.bmp"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "$(WELCOME_TITLE)"
!define MUI_WELCOMEPAGE_TEXT "$(WELCOME_TEXT)"
!define MUI_FINISHPAGE_TITLE "$(FINISH_TITLE)"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "$(FINISH_RUN)"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp

; language picker shown when the installer starts (remembered for the next time)
!define MUI_LANGDLL_REGISTRY_ROOT "HKCU"
!define MUI_LANGDLL_REGISTRY_KEY "${UNINST_KEY}"
!define MUI_LANGDLL_REGISTRY_VALUENAME "InstallerLanguage"

Var ThemeChoice
Var RadioAuto
Var RadioDark
Var RadioLight

!insertmacro MUI_PAGE_WELCOME
Page custom ThemePageCreate ThemePageLeave
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; English first: it is the default language of the installer
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "PortugueseBR"
!insertmacro MUI_LANGUAGE "Spanish"

; ---------- texts
LangString WELCOME_TITLE ${LANG_ENGLISH} "Welcome to the ${APP_NAME} Setup"
LangString WELCOME_TITLE ${LANG_PORTUGUESEBR} "Bem-vindo ao Instalador do ${APP_NAME}"
LangString WELCOME_TITLE ${LANG_SPANISH} "Bienvenido al instalador de ${APP_NAME}"

LangString WELCOME_TEXT ${LANG_ENGLISH} "Game Mode makes your games smoother and shows you what is going on, right on screen. You also get:$\r$\n$\r$\n* Priority for the game and less slowdown from other apps$\r$\n$\r$\n* Feather and Badlion style overlays, for Minecraft, Roblox and FNF$\r$\n$\r$\n* One profile per game, with automatic switching, and one-click import of your Steam and Epic Games$\r$\n$\r$\n* Movement Helper, brightness, shaders and Windows tweaks$\r$\n$\r$\n* Backups and an Undo button on every tweak that touches Windows"
LangString WELCOME_TEXT ${LANG_PORTUGUESEBR} "Ao instalar o Game Mode, você deixa seus jogos mais fluidos e acompanha tudo na tela. Você também terá:$\r$\n$\r$\n* Prioridade para o jogo e menos lentidão dos outros apps$\r$\n$\r$\n* Overlays estilo Feather e Badlion, para Minecraft, Roblox e FNF$\r$\n$\r$\n* Um perfil por jogo, com troca automática, e importação dos seus jogos da Steam e da Epic Games$\r$\n$\r$\n* Movement Helper, brilho, shaders e ajustes do Windows$\r$\n$\r$\n* Backup e botão Desfazer nos ajustes que mexem no Windows"
LangString WELCOME_TEXT ${LANG_SPANISH} "Al instalar Game Mode, tus juegos van más fluidos y ves todo en pantalla. También tendrás:$\r$\n$\r$\n* Prioridad para el juego y menos lentitud de las otras apps$\r$\n$\r$\n* Overlays estilo Feather y Badlion, para Minecraft, Roblox y FNF$\r$\n$\r$\n* Un perfil por juego, con cambio automático, e importación de tus juegos de Steam y Epic Games$\r$\n$\r$\n* Movement Helper, brillo, shaders y ajustes de Windows$\r$\n$\r$\n* Copia de seguridad y botón Deshacer en los ajustes que tocan Windows"

LangString FINISH_TITLE ${LANG_ENGLISH} "Installation complete"
LangString FINISH_TITLE ${LANG_PORTUGUESEBR} "Instalação concluída"
LangString FINISH_TITLE ${LANG_SPANISH} "Instalación completada"

LangString FINISH_RUN ${LANG_ENGLISH} "Open Game Mode now"
LangString FINISH_RUN ${LANG_PORTUGUESEBR} "Abrir o Game Mode agora"
LangString FINISH_RUN ${LANG_SPANISH} "Abrir Game Mode ahora"

LangString THEME_TITLE ${LANG_ENGLISH} "Appearance"
LangString THEME_TITLE ${LANG_PORTUGUESEBR} "Aparência"
LangString THEME_TITLE ${LANG_SPANISH} "Apariencia"

LangString THEME_SUB ${LANG_ENGLISH} "Choose the light or dark theme."
LangString THEME_SUB ${LANG_PORTUGUESEBR} "Escolha o tema claro ou escuro."
LangString THEME_SUB ${LANG_SPANISH} "Elige el tema claro u oscuro."

LangString THEME_TEXT ${LANG_ENGLISH} "Pick how Game Mode should look. You can change this later in Options > Accessibility."
LangString THEME_TEXT ${LANG_PORTUGUESEBR} "Escolha a aparência do Game Mode. Dá para mudar depois em Opções > Acessibilidade."
LangString THEME_TEXT ${LANG_SPANISH} "Elige el aspecto de Game Mode. Puedes cambiarlo después en Opciones > Accesibilidad."

LangString THEME_AUTO ${LANG_ENGLISH} "Automatic (same as Windows)"
LangString THEME_AUTO ${LANG_PORTUGUESEBR} "Automático (igual ao Windows)"
LangString THEME_AUTO ${LANG_SPANISH} "Automático (igual que Windows)"

LangString THEME_DARK ${LANG_ENGLISH} "Dark theme"
LangString THEME_DARK ${LANG_PORTUGUESEBR} "Tema escuro"
LangString THEME_DARK ${LANG_SPANISH} "Tema oscuro"

LangString THEME_LIGHT ${LANG_ENGLISH} "Light theme"
LangString THEME_LIGHT ${LANG_PORTUGUESEBR} "Tema claro"
LangString THEME_LIGHT ${LANG_SPANISH} "Tema claro"

LangString SEC_MAIN ${LANG_ENGLISH} "Game Mode"
LangString SEC_MAIN ${LANG_PORTUGUESEBR} "Game Mode"
LangString SEC_MAIN ${LANG_SPANISH} "Game Mode"

LangString SEC_DESKTOP ${LANG_ENGLISH} "Desktop shortcut"
LangString SEC_DESKTOP ${LANG_PORTUGUESEBR} "Atalho na Área de Trabalho"
LangString SEC_DESKTOP ${LANG_SPANISH} "Acceso directo en el Escritorio"

LangString SEC_MENU ${LANG_ENGLISH} "Start Menu shortcut"
LangString SEC_MENU ${LANG_PORTUGUESEBR} "Atalho no Menu Iniciar"
LangString SEC_MENU ${LANG_SPANISH} "Acceso directo en el menú Inicio"

LangString DESC_MAIN ${LANG_ENGLISH} "Game Mode and its uninstaller. Python is not needed."
LangString DESC_MAIN ${LANG_PORTUGUESEBR} "O Game Mode e o desinstalador. Não precisa de Python."
LangString DESC_MAIN ${LANG_SPANISH} "Game Mode y el desinstalador. No necesita Python."

LangString DESC_DESKTOP ${LANG_ENGLISH} "A Game Mode icon on the Desktop."
LangString DESC_DESKTOP ${LANG_PORTUGUESEBR} "Um ícone do Game Mode na Área de Trabalho."
LangString DESC_DESKTOP ${LANG_SPANISH} "Un icono de Game Mode en el Escritorio."

LangString DESC_MENU ${LANG_ENGLISH} "Game Mode in the Start Menu list."
LangString DESC_MENU ${LANG_PORTUGUESEBR} "O Game Mode na lista do Menu Iniciar."
LangString DESC_MENU ${LANG_SPANISH} "Game Mode en la lista del menú Inicio."

LangString UN_ASK ${LANG_ENGLISH} "Uninstall Game Mode?$\r$\n$\r$\nIf you used QoS, the Windows game tweaks or the Xbox Game Bar, open Game Mode and click Undo on them before you continue."
LangString UN_ASK ${LANG_PORTUGUESEBR} "Desinstalar o Game Mode?$\r$\n$\r$\nSe você usou QoS, os ajustes do Windows para jogos ou o Xbox Game Bar, abra o Game Mode e clique em Desfazer neles antes de continuar."
LangString UN_ASK ${LANG_SPANISH} "¿Desinstalar Game Mode?$\r$\n$\r$\nSi usaste QoS, los ajustes de Windows para juegos o la Xbox Game Bar, abre Game Mode y pulsa Deshacer en ellos antes de continuar."

LangString UN_DATA ${LANG_ENGLISH} "Also delete your Game Mode settings?"
LangString UN_DATA ${LANG_PORTUGUESEBR} "Apagar também as suas configurações do Game Mode?"
LangString UN_DATA ${LANG_SPANISH} "¿Borrar también tu configuración de Game Mode?"

VIProductVersion "${APP_VERSION}.0.0"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductName" "${APP_NAME}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileDescription" "${APP_NAME} installer"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "ProductName" "${APP_NAME}"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "FileDescription" "Instalador do ${APP_NAME}"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_SPANISH} "ProductName" "${APP_NAME}"
VIAddVersionKey /LANG=${LANG_SPANISH} "FileDescription" "Instalador de ${APP_NAME}"
VIAddVersionKey /LANG=${LANG_SPANISH} "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_SPANISH} "ProductVersion" "${APP_VERSION}"

; ---------- start: language picker (skipped in a silent update, which uses the Windows language)
Function .onInit
  StrCpy $ThemeChoice "auto"
  IfSilent skip_lang
    !insertmacro MUI_LANGDLL_DISPLAY
  skip_lang:
FunctionEnd

; ---------- theme page
Function ThemePageCreate
  !insertmacro MUI_HEADER_TEXT "$(THEME_TITLE)" "$(THEME_SUB)"
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}
  ${NSD_CreateLabel} 0 0 100% 24u "$(THEME_TEXT)"
  Pop $0
  ${NSD_CreateRadioButton} 10u 34u 90% 12u "$(THEME_AUTO)"
  Pop $RadioAuto
  ${NSD_AddStyle} $RadioAuto ${WS_GROUP}
  ${NSD_CreateRadioButton} 10u 52u 90% 12u "$(THEME_DARK)"
  Pop $RadioDark
  ${NSD_CreateRadioButton} 10u 70u 90% 12u "$(THEME_LIGHT)"
  Pop $RadioLight
  ${If} $ThemeChoice == "dark"
    ${NSD_Check} $RadioDark
  ${ElseIf} $ThemeChoice == "light"
    ${NSD_Check} $RadioLight
  ${Else}
    ${NSD_Check} $RadioAuto
  ${EndIf}
  nsDialogs::Show
FunctionEnd

Function ThemePageLeave
  ${NSD_GetState} $RadioDark $0
  ${NSD_GetState} $RadioLight $1
  ${If} $0 == ${BST_CHECKED}
    StrCpy $ThemeChoice "dark"
  ${ElseIf} $1 == ${BST_CHECKED}
    StrCpy $ThemeChoice "light"
  ${Else}
    StrCpy $ThemeChoice "auto"
  ${EndIf}
FunctionEnd

; A silent install (/S) is the automatic update: it opens the program again at the end.
Function .onInstSuccess
  IfSilent 0 not_silent
    SetOutPath "$INSTDIR\app"
    Exec '"$INSTDIR\app\${APP_EXE}"'
  not_silent:
FunctionEnd

Function LaunchApp
  SetOutPath "$INSTDIR\app"
  Exec '"$INSTDIR\app\${APP_EXE}"'
FunctionEnd

; ---------- install (everything of the program goes in the "app" subfolder, which is ours alone)
Section "$(SEC_MAIN)" SecMain
  SectionIn RO

  ; close Game Mode if it is open (polite request, no force) and wait for it to leave
  nsExec::ExecToLog 'taskkill /IM "${APP_EXE}"'
  StrCpy $R9 0
  wait_exit:
    ClearErrors
    Delete "$INSTDIR\app\${APP_EXE}"
    IfErrors 0 exit_ok
    IntOp $R9 $R9 + 1
    IntCmp $R9 15 exit_ok 0 exit_ok
    Sleep 1000
    Goto wait_exit
  exit_ok:

  RMDir /r "$INSTDIR\app"
  SetOutPath "$INSTDIR\app"
  File /r "${DIST}\*.*"

  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\Desinstalar.exe"

  ; what was picked here (language and theme). The app reads it, but anything the person
  ; later chooses in Options > Accessibility wins. Not written during a silent update.
  IfSilent skip_prefs
    CreateDirectory "${DATA_DIR}"
    StrCpy $0 "en"
    ${If} $LANGUAGE == ${LANG_PORTUGUESEBR}
      StrCpy $0 "pt"
    ${ElseIf} $LANGUAGE == ${LANG_SPANISH}
      StrCpy $0 "es"
    ${EndIf}
    FileOpen $1 "${DATA_DIR}\installer_prefs.json" w
    FileWrite $1 '{"lang": "$0", "theme": "$ThemeChoice"}'
    FileClose $1
  skip_prefs:

  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "${APP_NAME}"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\app\${APP_EXE}"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD HKCU "${UNINST_KEY}" "EstimatedSize" $0
SectionEnd

Section "$(SEC_DESKTOP)" SecDesktop
  ; in a silent update, only remake the shortcut if it already existed (respects who deleted it)
  IfSilent 0 dt_make
  IfFileExists "$DESKTOP\${APP_NAME}.lnk" dt_make dt_skip
  dt_make:
  SetOutPath "$INSTDIR\app"
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\app\${APP_EXE}" "" "$INSTDIR\app\${APP_EXE}" 0 "" "" "${APP_NAME}"
  dt_skip:
SectionEnd

Section "$(SEC_MENU)" SecMenu
  IfSilent 0 mn_make
  IfFileExists "$SMPROGRAMS\${APP_NAME}.lnk" mn_make mn_skip
  mn_make:
  SetOutPath "$INSTDIR\app"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}.lnk" "$INSTDIR\app\${APP_EXE}" "" "$INSTDIR\app\${APP_EXE}" 0 "" "" "${APP_NAME}"
  mn_skip:
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "$(DESC_MAIN)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "$(DESC_DESKTOP)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMenu} "$(DESC_MENU)"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ---------- uninstall
Function un.onInit
  !insertmacro MUI_UNGETLANGUAGE
  MessageBox MB_YESNO|MB_ICONQUESTION "$(UN_ASK)" /SD IDYES IDYES un_go
  Abort
  un_go:
FunctionEnd

Section "Uninstall"
  nsExec::ExecToLog 'taskkill /IM "${APP_EXE}"'
  Sleep 1500

  Delete "$DESKTOP\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}.lnk"
  DeleteRegValue HKCU "${RUN_KEY}" "${RUN_NAME}"

  RMDir /r "$INSTDIR\app"
  Delete "$INSTDIR\Desinstalar.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINST_KEY}"

  MessageBox MB_YESNO|MB_ICONQUESTION "$(UN_DATA)" /SD IDNO IDNO un_keep
    RMDir /r "${DATA_DIR}"
  un_keep:
SectionEnd
