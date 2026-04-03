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
        'status' => 'error',
        'message' => 'DB接続失敗',
        'detail' => $e->getMessage(),
    ]);
    exit;
}

// ==========================
// JSON受信
// ==========================
$raw = file_get_contents('php://input');
$data = json_decode($raw, true);

if (!$data || !isset($data['events']) || !isset($data['scopes']) || !isset($data['sync_run_id'])) {
    http_response_code(400);
    echo json_encode([
        'status' => 'error',
        'message' => '不正なリクエスト (events/scopes/sync_run_id required)',
    ]);
    exit;
}

$events = $data['events'];
$scopes = $data['scopes']; // [{"calendar_id":"xxx","event_date":"2026-01-20"}, ...]
$syncRunId = (string)$data['sync_run_id'];

try {
    $pdo->beginTransaction();

    // ==========================
    // INSERT / UPDATE（同期run_idを付与して生存扱いにする）
    // ==========================
    $sql = "
    INSERT INTO calendar_events (
        calendar_id,
        calendar_name,
        event_date,
        start_time,
        end_time,
        is_all_day,
        title,
        actor_name,
        customer_name,
        sales_name,
        detail,
        event_url,
        scraped_at,
        sync_cnt,
        last_seen_run,
        is_deleted,
        deleted_at
    ) VALUES (
        :calendar_id,
        :calendar_name,
        :event_date,
        :start_time,
        :end_time,
        :is_all_day,
        :title,
        :actor_name,
        :customer_name,
        :sales_name,
        :detail,
        :event_url,
        :scraped_at,
        0,
        :last_seen_run,
        0,
        NULL
    )
    ON DUPLICATE KEY UPDATE
        calendar_name  = VALUES(calendar_name),
        event_date     = VALUES(event_date),
        start_time     = VALUES(start_time),
        end_time       = VALUES(end_time),
        is_all_day     = VALUES(is_all_day),
        title          = VALUES(title),
        actor_name     = VALUES(actor_name),
        customer_name  = VALUES(customer_name),
        sales_name     = VALUES(sales_name),
        detail         = VALUES(detail),
        event_url      = VALUES(event_url),
        scraped_at     = VALUES(scraped_at),
        sync_cnt       = sync_cnt + 1,
        last_seen_run  = VALUES(last_seen_run),
        is_deleted     = 0,
        deleted_at     = NULL
    ";

    $stmt = $pdo->prepare($sql);

    foreach ($events as $e) {
        // ここで必須項目が欠けてると事故るので最低限ガード
        if (empty($e['calendar_id']) || empty($e['calendar_name']) || empty($e['date']) || empty($e['event_url'])) {
            continue;
        }

        $stmt->execute([
            ':calendar_id'   => $e['calendar_id'],
            ':calendar_name' => $e['calendar_name'],
            ':event_date'    => $e['date'],
            ':start_time'    => $e['start_time'] ?? '',
            ':end_time'      => $e['end_time'] ?? '',
            ':is_all_day'    => (($e['start_time'] ?? '') === '終日') ? 1 : 0,
            ':title'         => $e['title'] ?? '',
            ':actor_name'    => $e['actor_name'] ?? null,
            ':customer_name' => $e['customer_name'] ?? null,
            ':sales_name'    => $e['sales_name'] ?? null,
            ':detail'        => $e['detail'] ?? '',
            ':event_url'     => $e['event_url'],
            ':scraped_at'    => $e['scraped_at'] ?? date('Y-m-d H:i:s'),
            ':last_seen_run' => $syncRunId,
        ]);
    }

    // ==========================
    // 削除反映（scopes内で今回見えてない予定を is_deleted=1）
    // ==========================
    $delStmt = $pdo->prepare("
        UPDATE calendar_events
        SET is_deleted = 1,
            deleted_at = NOW()
        WHERE calendar_id = :calendar_id
          AND event_date  = :event_date
          AND (last_seen_run IS NULL OR last_seen_run <> :last_seen_run)
          AND is_deleted = 0
    ");

    $deletedTotal = 0;

    foreach ($scopes as $s) {
        if (empty($s['calendar_id']) || empty($s['event_date'])) continue;

        $delStmt->execute([
            ':calendar_id'   => $s['calendar_id'],
            ':event_date'    => $s['event_date'],
            ':last_seen_run' => $syncRunId,
        ]);

        $deletedTotal += $delStmt->rowCount();
    }

    $pdo->commit();

    echo json_encode([
        'status' => 'ok',
        'count'  => count($events),
        'deleted' => $deletedTotal,
        'sync_run_id' => $syncRunId,
        'scope_count' => count($scopes),
    ]);

} catch (Exception $e) {
    $pdo->rollBack();
    http_response_code(500);
    echo json_encode([
        'status' => 'error',
        'message' => '保存失敗',
        'detail' => $e->getMessage(),
    ]);
}
