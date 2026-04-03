<?php
header('Content-Type: application/json');
require __DIR__ . '/db.php';

$data = json_decode(file_get_contents('php://input'), true);

$id     = $data['id'] ?? null;
$status = $data['status'] ?? 'done';
$msg    = $data['message'] ?? null;

$stmt = $pdo->prepare("
    UPDATE scrape_requests
    SET
      status = :status,
      finished_at = NOW(),
      message = :message
    WHERE id = :id
");
$stmt->execute([
    ':id'      => $id,
    ':status'  => $status,
    ':message' => $msg
]);

echo json_encode(['status' => 'ok']);
