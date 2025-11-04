<?php
// CORS設定(開発環境用)
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST');
header('Access-Control-Allow-Headers: Content-Type');
header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        // POSTデータを取得
        $input = json_decode(file_get_contents('php://input'), true);
        
        if (!isset($input['municipality']) || !isset($input['field']) || !isset($input['value'])) {
            throw new Exception('必須パラメータが不足しています');
        }
        
        $municipality = $input['municipality'];
        $field = $input['field'];
        $value = $input['value'];
        
        // data-integrated.jsonを読み込み
        $jsonFile = __DIR__ . '/data-integrated.json';
        
        if (!file_exists($jsonFile)) {
            throw new Exception('data-integrated.jsonが見つかりません');
        }
        
        $jsonData = file_get_contents($jsonFile);
        $data = json_decode($jsonData, true);
        
        if ($data === null) {
            throw new Exception('JSONのパースに失敗しました');
        }
        
        // municipality_infoを更新
        if (!isset($data['municipality_info'][$municipality])) {
            throw new Exception("自治体 '$municipality' が見つかりません");
        }
        
        $oldValue = $data['municipality_info'][$municipality][$field] ?? null;
        $data['municipality_info'][$municipality][$field] = $value;
        
        // バックアップを作成
        $backupFile = __DIR__ . '/data-integrated.backup.' . date('YmdHis') . '.json';
        file_put_contents($backupFile, $jsonData);
        
        // 更新したJSONを保存
        $newJsonData = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
        
        if (file_put_contents($jsonFile, $newJsonData) === false) {
            throw new Exception('ファイルの保存に失敗しました');
        }
        
        // 成功レスポンス
        echo json_encode([
            'success' => true,
            'message' => '保存しました',
            'municipality' => $municipality,
            'field' => $field,
            'oldValue' => $oldValue,
            'newValue' => $value,
            'backup' => basename($backupFile)
        ], JSON_UNESCAPED_UNICODE);
        
    } catch (Exception $e) {
        http_response_code(500);
        echo json_encode([
            'success' => false,
            'error' => $e->getMessage()
        ], JSON_UNESCAPED_UNICODE);
    }
} else {
    http_response_code(405);
    echo json_encode([
        'success' => false,
        'error' => 'POSTメソッドのみ受け付けます'
    ], JSON_UNESCAPED_UNICODE);
}
?>
