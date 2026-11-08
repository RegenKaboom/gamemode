; Instalador do Game Mode (programa compilado: NÃO precisa de Python).
; Antes de compilar este roteiro, o programa precisa estar compilado em build\gamemode_app.dist
; (veja o COMPILAR.txt). Depois: botão direito neste arquivo > "Compile NSIS Script".

Unicode true
!define APP_NAME "Game Mode"
!ifndef APP_VERSION
  !define APP_VERSION "2.4"
!endif
!define APP_EXE "GameMode.exe"
!define DIST "build\gamemode_app.dist"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\GameMode"
!define RUN_KEY "Software\Microsoft\Windows\CurrentVersion\Run"
!define RUN_NAME "GameModeLite"

!if /FileExists "${__FILEDIR__}\${DIST}\${APP_EXE}"
!else
  !error "Falta o programa compilado em ${DIST}. Compile o Game Mode primeiro (veja o COMPILAR.txt)."
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
!insertmacro GetSize

; ---------- aparência (painel preto à esquerda, como o instalador do Steam)
!define MUI_ICON "app.ico"
!define MUI_UNICON "app.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "welcome.bmp"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "Bem-vindo ao Instalador do ${APP_NAME}"
!define MUI_WELCOMEPAGE_TEXT "Ao instalar o Game Mode, você deixa seus jogos mais fluidos e acompanha tudo na tela. Você também terá:$\r$\n$\r$\n* Prioridade para o jogo e menos lentidão dos outros apps$\r$\n$\r$\n* Overlays estilo Feather e Badlion, para Minecraft, Roblox e FNF$\r$\n$\r$\n* Perfis para vários jogos, com troca automática$\r$\n$\r$\n* Movement Helper, brilho, shaders e ajustes do Windows$\r$\n$\r$\n* Backup e botão Desfazer nos ajustes que mexem no Windows"

!define MUI_FINISHPAGE_TITLE "Instalação concluída"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Abrir o Game Mode agora"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "PortugueseBR"

VIProductVersion "${APP_VERSION}.0.0"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "ProductName" "${APP_NAME}"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "FileDescription" "Instalador do ${APP_NAME}"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=${LANG_PORTUGUESEBR} "ProductVersion" "${APP_VERSION}"

; Instalação silenciosa (/S) é a atualização automática: abre o programa de novo no final.
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

; ---------- instalar (tudo do programa fica na subpasta "app", que é só nossa)
Section "!Game Mode" SecMain
  SectionIn RO

  ; fecha o Game Mode se estiver aberto (pedido educado, sem forçar) e espera ele sair
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

Section "Atalho na Área de Trabalho" SecDesktop
  ; na atualização silenciosa, só refaz o atalho se ele já existia (respeita quem apagou)
  IfSilent 0 dt_make
  IfFileExists "$DESKTOP\${APP_NAME}.lnk" dt_make dt_skip
  dt_make:
  SetOutPath "$INSTDIR\app"
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\app\${APP_EXE}" "" "$INSTDIR\app\${APP_EXE}" 0 "" "" "${APP_NAME}"
  dt_skip:
SectionEnd

Section "Atalho no Menu Iniciar" SecMenu
  IfSilent 0 mn_make
  IfFileExists "$SMPROGRAMS\${APP_NAME}.lnk" mn_make mn_skip
  mn_make:
  SetOutPath "$INSTDIR\app"
  CreateShortCut "$SMPROGRAMS\${APP_NAME}.lnk" "$INSTDIR\app\${APP_EXE}" "" "$INSTDIR\app\${APP_EXE}" 0 "" "" "${APP_NAME}"
  mn_skip:
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "O Game Mode e o desinstalador. Não precisa de Python."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Um ícone do Game Mode na Área de Trabalho."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMenu} "O Game Mode na lista do Menu Iniciar."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ---------- desinstalar
Function un.onInit
  MessageBox MB_YESNO|MB_ICONQUESTION "Desinstalar o Game Mode?$\r$\n$\r$\nSe você usou QoS, os ajustes do Windows para jogos ou o Xbox Game Bar, abra o Game Mode e clique em Desfazer neles antes de continuar." /SD IDYES IDYES un_go
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

  MessageBox MB_YESNO|MB_ICONQUESTION "Apagar também as suas configurações do Game Mode?" /SD IDNO IDNO un_keep
    RMDir /r "$APPDATA\GameModeLite"
  un_keep:
SectionEnd
