# 启动 Neo4j 5.26（免安装），默认监听 127.0.0.1:7687 / 7474
# 用法：先把 Neo4j 解压到纯英文路径，再设置 NEO4J_HOME，例如：
#   $env:NEO4J_HOME = "C:\Users\<you>\neo4j-community-5.26.0"
#   .\scripts\start_neo4j.ps1
$ErrorActionPreference = "Stop"
$neo4jRoot = $env:NEO4J_HOME
if (-not $neo4jRoot) {
  $local = Join-Path $PSScriptRoot "..\tools\neo4j-community-5.26.0"
  if (-not (Test-Path $local)) {
    throw "Neo4j not found. Set NEO4J_HOME to an ASCII path, e.g. C:\Users\<you>\neo4j-community-5.26.0"
  }
  $neo4jRoot = $local
}
$neo4jRoot = (Resolve-Path $neo4jRoot).Path
if ($neo4jRoot -match '[^\x00-\x7F]') {
  Write-Warning "NEO4J_HOME contains non-ASCII characters; Neo4j 5.26 may fail to resolve the path. Use an ASCII path."
}
$env:NEO4J_HOME = $neo4jRoot
Write-Host "NEO4J_HOME = $env:NEO4J_HOME"
java -cp "$neo4jRoot\lib\*" "-Dlog4j2.configurationFile=$neo4jRoot\conf\server-logs.xml" `
  org.neo4j.server.CommunityEntryPoint "--home-dir=$neo4jRoot" "--config-dir=$neo4jRoot\conf"
