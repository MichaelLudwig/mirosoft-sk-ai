# PowerShell Script to check Python dependencies
Write-Host "=== Python Dependency Check ===" -ForegroundColor Green
Write-Host ""

# Check Python version
Write-Host "Python Version:" -ForegroundColor Yellow
python --version
Write-Host ""

# Check pip version
Write-Host "Pip Version:" -ForegroundColor Yellow
pip --version
Write-Host ""

# Check installed packages
Write-Host "Checking required packages:" -ForegroundColor Yellow
Write-Host ""

$packages = @(
    "streamlit",
    "semantic-kernel",
    "aiohttp",
    "azure-identity",
    "python-dotenv"
)

foreach ($package in $packages) {
    $result = pip show $package 2>$null
    if ($LASTEXITCODE -eq 0) {
        $version = ($result | Select-String "Version:").ToString().Split(" ")[1]
        Write-Host "✓ $package is installed (Version: $version)" -ForegroundColor Green
    } else {
        Write-Host "✗ $package is NOT installed" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Semantic Kernel Details ===" -ForegroundColor Yellow
pip show semantic-kernel

Write-Host ""
Write-Host "=== Environment Variables Check ===" -ForegroundColor Yellow
$envVars = @(
    "AZURE_OPENAI_KEY",
    "AZURE_OPENAI_ENDPOINT", 
    "AZURE_OPENAI_DEPLOYMENT_NAME",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET"
)

foreach ($var in $envVars) {
    if ([Environment]::GetEnvironmentVariable($var)) {
        Write-Host "✓ $var is set" -ForegroundColor Green
    } else {
        Write-Host "✗ $var is NOT set" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "To install missing packages, run:" -ForegroundColor Cyan
Write-Host "pip install -r requirements.txt"