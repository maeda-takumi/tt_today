<?php
header('Content-Type: application/json');
require __DIR__ . '/db.php';

$data = json_decode(file_get_contents('php://input'), true);
$id = $data['id'] ?? null;

if (!$id) {
    http_response_code(400);
    echo json_encode(['status' => 'error', 'locked' => false]);
    exit;
}

$stmt = $pdo->prepare("
    UPDATE scrape_requests
    SET status = 'running', started_at = NOW()
    WHERE id = :id AND status = 'pending'
");
$stmt->execute([':id' => $id]);

$locked = ($stmt->rowCount() === 1);

echo json_encode([
    'status' => 'ok',
    'locked' => $locked
], JSON_UNESCAPED_UNICODE);
