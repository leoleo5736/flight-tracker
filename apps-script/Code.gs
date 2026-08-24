/**
 * 機票價格接收器 — Google Apps Script Web App
 *
 * 這支程式的工作只有一件事:
 * 接收 GitHub 每天送來的價格, 貼到試算表最下面一行。
 *
 * 安裝方式請看 README.md 的「步驟三」。
 */

// 要寫入的工作表名稱(分頁名稱)。沒有的話程式會自動建立。
var SHEET_NAME = '機票價格';

// 一組你自己隨便設的密碼, 防止別人亂送資料進來。
// 請改成你自己的字串, 並且跟 GitHub Secret 裡的 SHEET_TOKEN 設成一樣。
var SECRET_TOKEN = '請改成你自己的密碼abc123';

var HEADER = [
  '抓取時間', '去程航班', '去程日期', '去程起飛', '去程抵達',
  '回程日期', '機型', '飛行分鐘', '來回總價TWD'
];

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);

    if (SECRET_TOKEN && body.token !== SECRET_TOKEN) {
      return reply({ ok: false, error: '密碼不對' });
    }

    var rows = body.rows || [];
    if (rows.length === 0) {
      return reply({ ok: false, error: '沒有資料' });
    }

    var sheet = getSheet();
    sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, HEADER.length)
         .setValues(rows);

    return reply({ ok: true, added: rows.length });
  } catch (err) {
    return reply({ ok: false, error: String(err) });
  }
}

// 用瀏覽器打開網址時會看到這個, 用來確認部署成功
function doGet() {
  return reply({ ok: true, message: '機票價格接收器運作中' });
}

function getSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADER);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function reply(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
