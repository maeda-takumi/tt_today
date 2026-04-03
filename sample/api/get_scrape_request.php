<?php
header('Content-Type: application/json');
require __DIR__ . '/db.php'; // PDO $pdo を用意する前提

// すでに running があれば何もしない
$running = $pdo->query("
    SELECT id FROM scrape_requests
    WHERE status = 'running'
    LIMIT 1
")->fetch();

if ($running) {
    echo json_encode(['status' => 'ok', 'request' => null]);
    exit;
}

// pending を1件取得
$stmt = $pdo->query("
    SELECT *
    FROM scrape_requests
    WHERE status = 'pending'
    ORDER BY requested_at ASC
    LIMIT 1
");

$req = $stmt->fetch(PDO::FETCH_ASSOC);

echo json_encode([
    'status'  => 'ok',
    'request' => $req ?: null
], JSON_UNESCAPED_UNICODE);
