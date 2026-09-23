FROM python:3.13.5-slim
WORKDIR /app
COPY app.py deployment-manifest.json build-info.json ./
COPY public ./public
USER 65532:65532
ENV APP_NETWORK=sepolia PORT=8080 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health', timeout=2)"
CMD ["python", "app.py"]
