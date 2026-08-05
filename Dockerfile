# 세무법인 지율 홈페이지 - 컨테이너 이미지
# Koyeb / Fly.io / Cloud Run / Railway 등 컨테이너 호스트에서 그대로 배포됩니다.
FROM python:3.12-slim

WORKDIR /app
COPY . .

# 세무칼럼: content/*.md → data/posts.json 재빌드.
# 관리자가 GitHub에서 content/의 .md 원고를 직접 수정하면, 배포 시 이 단계에서
# posts.json 이 다시 생성되어 홈페이지에 자동 반영됩니다. (표준 라이브러리만 사용)
RUN python build_posts.py

# 외부 접속 허용. PORT 는 호스트가 주입(없으면 8080).
ENV HOST=0.0.0.0
# 리드(상담신청) DB 저장 위치를 쓰기 가능한 별도 폴더로.
# (Cloudtype 등은 컨테이너를 비루트로 실행 → /app 하위에 쓰기 불가 → sqlite "unable to open" 방지)
ENV JIYUL_DATA_DIR=/data
RUN mkdir -p /data && chmod 777 /data
EXPOSE 8080

# 표준 라이브러리만 사용 → 설치할 패키지 없음
CMD ["python", "server.py"]
