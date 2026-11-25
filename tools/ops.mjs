// 管理用の道具（GitHub の上でだけ動かす）
//   node tools/ops.mjs test  … ルールがねらいどおりに働くか、ためし用の場所（kaihotest）で確かめる
//   node tools/ops.mjs reset … kaiho の記録（人数・識別番号）を全部消して、まっさらにする
import fs from 'fs';
import { token, api, DBURL } from './fb.mjs';
const op = process.argv[2];
const KEY = 'AIzaSyAcJgJLVbuvx85_qEGJe1WhwsOelidxeYk', REF = { Referer: 'https://nasubi-no-oniwa.com/', Origin: 'https://nasubi-no-oniwa.com' };
const tk = await token();
if (op === 'reset') {
  const before = await api('GET', '/kaiho/kc.json', undefined, tk); console.log('消す前の識別番号：', before);
  await api('DELETE', '/kaiho.json', undefined, tk); console.log('kaiho の記録を消しました：', await api('GET', '/kaiho.json', undefined, tk)); process.exit(0);
}
if (op !== 'test') { console.log('op は test か reset'); process.exit(1); }
const T = 'kaihotest';
const rulesTxt = await api('GET', '/.settings/rules.json', undefined, tk); const all = JSON.parse(rulesTxt);
const mine = JSON.parse(fs.readFileSync('database.rules.kaiho.json', 'utf8').split("'kaiho/").join("'" + T + "/"));
all.rules[T] = mine; await api('PUT', '/.settings/rules.json', JSON.stringify(all, null, 2), tk); await api('DELETE', '/' + T + '.json', undefined, tk);
let fail = 0;
try {
  const su = await fetch('https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=' + KEY, { method: 'POST', headers: { 'Content-Type': 'application/json', ...REF }, body: JSON.stringify({ returnSecureToken: true }) });
  const sj = await su.json(); if (!sj.idToken) throw new Error('匿名ログインに失敗 ' + JSON.stringify(sj).slice(0, 200)); const A = '?auth=' + encodeURIComponent(sj.idToken);
  const req = async (m, p, b, q) => { const r = await fetch(DBURL + '/' + T + (p ? '/' + p : '') + '.json' + (q === 'anon' ? '' : A) + (q && q !== 'anon' ? '&' + q : ''), { method: m, headers: { 'Content-Type': 'application/json', ...REF }, body: b === undefined ? undefined : JSON.stringify(b) }); return { ok: r.ok, s: r.status, j: await r.json().catch(() => null) }; };
  const want = async (label, exp, m, p, b, q) => { const r = await req(m, p, b, q); const good = r.ok === exp; if (!good) fail++; console.log((good ? '○' : '×'), label, '→', r.s, good ? '' : JSON.stringify(r.j).slice(0, 160)); return r; };
  const H1 = 'aaaaaaaa01', H2 = 'aaaaaaaa02', K1 = 'kkkkkkkk01', K2 = 'kkkkkkkk02', K3 = 'kkkkkkkk03';
  await want('人数：1人目を数える', true, 'PATCH', '', { ['u/' + H1]: 'b3', 'n/b3': { c: 1, h: H1 } });
  await want('人数：同じ名前をもう一度（はじく）', false, 'PATCH', '', { ['u/' + H1]: 'b3', 'n/b3': { c: 2, h: H1 } });
  await want('人数：しるしなしで人数だけ増やす（はじく）', false, 'PUT', 'n/b3', { c: 2, h: 'zzzzzzzz99' });
  await want('人数：人数なしでしるしだけ（はじく）', false, 'PUT', 'u/' + H2, 'b3');
  await want('人数：とび番（はじく）', false, 'PATCH', '', { ['u/' + H2]: 'b3', 'n/b3': { c: 5, h: H2 } });
  await want('人数：区切りがちがう（はじく）', false, 'PATCH', '', { ['u/' + H2]: 'b4', 'n/b3': { c: 2, h: H2 } });
  await want('人数：2人目を数える', true, 'PATCH', '', { ['u/' + H2]: 'b3', 'n/b3': { c: 2, h: H2 } });
  await want('人数：別の区切りの1人目', true, 'PATCH', '', { 'u/aaaaaaaa03': 'b0', 'n/b0': { c: 1, h: 'aaaaaaaa03' } });
  await want('人数：ログインなし（はじく）', false, 'PATCH', '', { 'u/aaaaaaaa04': 'b1', 'n/b1': { c: 1, h: 'aaaaaaaa04' } }, 'anon');
  await want('怪獣：100号から始める（はじく）', false, 'PATCH', '', { kc: { c: 100, h: K1 }, ['k/' + K1]: { i: 100, n: 'てすと', f: 88 } });
  await want('怪獣：101号を登録', true, 'PATCH', '', { kc: { c: 101, h: K1 }, ['k/' + K1]: { i: 101, n: 'てすと', f: 88 } });
  await want('怪獣：同じ名前でもう一度（はじく）', false, 'PATCH', '', { kc: { c: 102, h: K1 }, ['k/' + K1]: { i: 102, n: 'てすと', f: 88 } });
  await want('怪獣：とび番 103号（はじく）', false, 'PATCH', '', { kc: { c: 103, h: K2 }, ['k/' + K2]: { i: 103, n: 'にばん', f: 90 } });
  await want('怪獣：番号だけ進める（はじく）', false, 'PUT', 'kc', { c: 102, h: K2 });
  await want('怪獣：番号を進めずに登録（はじく）', false, 'PUT', 'k/' + K2, { i: 150, n: 'にばん', f: 90 });
  await want('怪獣：フォルティチュード7.9（はじく）', false, 'PATCH', '', { kc: { c: 102, h: K2 }, ['k/' + K2]: { i: 102, n: 'にばん', f: 79 } });
  await want('怪獣：番号と中身が合わない（はじく）', false, 'PATCH', '', { kc: { c: 102, h: K2 }, ['k/' + K2]: { i: 101, n: 'にばん', f: 90 } });
  await want('怪獣：102号を登録', true, 'PATCH', '', { kc: { c: 102, h: K2 }, ['k/' + K2]: { i: 102, n: 'にばん', f: 99 } });
  await want('怪獣：登録ずみを書きかえる（はじく）', false, 'PUT', 'k/' + K1 + '/f', 99);
  await want('怪獣：登録ずみを消す（はじく）', false, 'DELETE', 'k/' + K1);
  await want('怪獣：15文字の名前で103号', true, 'PATCH', '', { kc: { c: 103, h: K3 }, ['k/' + K3]: { i: 103, n: 'あいうえおかきくけこさしすせそ', f: 80 } });
  let r = await want('読む：人数', true, 'GET', 'n', undefined, 'anon'); console.log('   ', JSON.stringify(r.j));
  r = await want('読む：いちばん新しい番号', true, 'GET', 'kc/c', undefined, 'anon'); if (r.j !== 103) { fail++; console.log('× 番号が 103 ではない', r.j); }
  r = await want('読む：名前のしるし1つ', true, 'GET', 'u/' + H1, undefined, 'anon'); if (r.j !== 'b3') { fail++; console.log('× しるしがちがう', r.j); }
  await want('読む：しるしを全部（はじく）', false, 'GET', 'u', undefined, 'anon');
  r = await fetch(DBURL + '/' + T + '/k.json?orderBy=%22i%22&startAt=101&limitToFirst=200', { headers: REF }); let j = await r.json(); let n = j ? Object.keys(j).length : 0; console.log(r.ok && n === 3 ? '○' : '×', '読む：一覧（番号順）→', r.status, n, '件'); if (!(r.ok && n === 3)) { fail++; console.log(JSON.stringify(j).slice(0, 200)); }
  r = await fetch(DBURL + '/' + T + '/k.json?orderBy=%22i%22&equalTo=102', { headers: REF }); j = await r.json(); const v = j && Object.values(j)[0]; console.log(r.ok && v && v.n === 'にばん' ? '○' : '×', '読む：番号でさがす（102号）→', r.status, JSON.stringify(j).slice(0, 120)); if (!(r.ok && v && v.n === 'にばん')) fail++;
  r = await fetch(DBURL + '/' + T + '/k.json?orderBy=%22i%22&equalTo=110', { headers: REF }); j = await r.json(); console.log(r.ok && (!j || !Object.keys(j).length) ? '○' : '×', '読む：まだいない番号（110号）→', r.status, JSON.stringify(j)); if (!(r.ok && (!j || !Object.keys(j).length))) fail++;
} catch (e) { fail++; console.log('× 途中で止まりました：', e.message); }
// あとかたづけ（ためし用の場所とルールを消す）
await api('DELETE', '/' + T + '.json', undefined, tk);
const cur = JSON.parse(await api('GET', '/.settings/rules.json', undefined, tk)); delete cur.rules[T]; await api('PUT', '/.settings/rules.json', JSON.stringify(cur, null, 2), tk);
console.log('ためし用の場所を消しました。残っている場所：', Object.keys(JSON.parse(await api('GET', '/.settings/rules.json', undefined, tk)).rules).join(' '));
console.log(fail ? '結果：' + fail + ' 個の × があります' : '結果：全部 ○');
process.exit(fail ? 1 : 0);
