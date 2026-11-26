import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [source, destination] = process.argv.slice(2);
const tables = JSON.parse(await fs.readFile(source, 'utf8'));
const workbook = Workbook.create();
for (const [index, [name, records]] of Object.entries(tables).entries()) {
  const sheet = workbook.worksheets.add(name);
  const width = records[0].length;
  const range = sheet.getRangeByIndexes(0, 0, records.length, width);
  range.values = records;
  sheet.tables.add(range, true, `StoryData${index}`);
  sheet.freezePanes.freezeRows(1);
  for (let column = 0; column < width; column++) {
    const max = Math.max(...records.map(row => Array.from(String(row[column] ?? '')).reduce((size, char) => size + (char.codePointAt(0) > 127 ? 2 : 1), 0)));
    sheet.getRangeByIndexes(0, column, 1, 1).format.columnWidth = Math.min(65, Math.max(12, max + 3));
  }
}
await (await SpreadsheetFile.exportXlsx(workbook)).save(destination);
