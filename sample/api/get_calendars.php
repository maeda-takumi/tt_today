<?php
header('Content-Type: application/json');

// ==========================
// DB設定
// ==========================
define('DB_HOST', 'localhost');
define('DB_NAME', 'ss911157_timetree');
define('DB_USER', 'ss911157_sedo');
define('DB_PASSWORD', 'sedorisedori');

try {
    $pdo = new PDO(
        "mysql:host=" . DB_HOST . ";dbname=" . DB_NAME . ";charset=utf8mb4",
        DB_USER,
        DB_PASSWORD,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        ]
    );
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'status'  => 'error',
        'message' => 'DB接続失敗',
        'detail'  => $e->getMessage(),
    ]);
    exit;
}

try {
    // ==========================
    // 有効なカレンダー取得
    // ==========================
    $stmt = $pdo->prepare("
        SELECT
            name,
            timetree_calendar_id
        FROM calendars
        WHERE is_active = 1
        ORDER BY sort_order ASC
    ");
    $stmt->execute();

    $calendars = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode([
        'status'    => 'ok',
        'count'     => count($calendars),
        'calendars' => $calendars,
    ], JSON_UNESCAPED_UNICODE);

} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'status'  => 'error',
        'message' => '取得失敗',
        'detail'  => $e->getMessage(),
    ]);
}
