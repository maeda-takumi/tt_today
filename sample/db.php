<?php
// timetree/db.php

$DB_HOST = 'localhost';
$DB_NAME = 'ss911157_timetree';
$DB_USER = 'ss911157_sedo';
$DB_PASS = 'sedorisedori';

try {
    $pdo = new PDO(
        "mysql:host={$DB_HOST};dbname={$DB_NAME};charset=utf8mb4",
        $DB_USER,
        $DB_PASS,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]
    );
} catch (PDOException $e) {
    // JSON を返す API なので、ここも JSON で落とす
    header('Content-Type: application/json; charset=utf-8');
    http_response_code(500);
    echo json_encode([
        'error' => 'DB connection failed',
        'message' => $e->getMessage(),
    ]);
    exit;
}
