이 폴더(files/)에 넣은 파일이 홈페이지 "자료실" 페이지에 자동으로 나타나고,
방문자가 다운로드할 수 있습니다.

■ 파일 추가 방법 (관리자)
  방법 A) GitHub 웹에서 업로드 (가장 쉬움)
    1. github.com/tax8980-coder/musical-train 접속 → 로그인
    2. files 폴더 열기 → "Add file" → "Upload files"
    3. 서식 파일을 끌어다 놓고 아래 "Commit changes" 클릭
    4. 1~2분 뒤 자동 배포되어 자료실에 표시됨
  방법 B) 이 files 폴더에 파일을 넣고 git commit & push

■ 표시 규칙
  - 파일 이름이 그대로 자료실의 제목이 됩니다.
    예) "세무대리 위임장.pdf" → 자료실에 "세무대리 위임장"으로 표시
  - 지원 형식: PDF, HWP/HWPX(한글), DOCX, XLSX, ZIP 등 무엇이든 가능
  - 이름이 . 또는 _ 로 시작하는 파일과 README 파일은 목록에서 제외됩니다.

■ 파일 삭제
  GitHub에서 해당 파일을 삭제(Delete)하고 commit 하면 자료실에서도 사라집니다.
