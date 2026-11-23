# 启动自带的 Neo4j 5.26（免安装），默认监听 127.0.0.1:7687 / 7474
$ErrorActionPreference = "Stop"
$home = Join-Path $PSScriptRoot "..\tools\neo4j-community-5.26.0" | Resolve-Path
$env:NEO4J_HOME = $home.Path
Write-Host "NEO4J_HOME = $env:NEO4J_HOME"
java -cp "$($home.Path)\lib\*" "-Dlog4j2.configurationFile=$($home.Path)\conf\server-logs.xml" `
  org.neo4j.server.CommunityEntryPoint "--home-dir=$($home.Path)" "--config-dir=$($home.Path)\conf"
