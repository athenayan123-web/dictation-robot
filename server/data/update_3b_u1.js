// 更新三年级下册第一单元
const fs = require('fs');
const filePath = 'E:/智能整理/dictation-robot/server/data/chinese_textbook.json';
const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));

const idx = data.grades.findIndex(g => g.grade === '三年级下册');
console.log('三年级下册索引:', idx);

// 只替换第一单元
const newUnit1 = {
  "unit": 1,
  "title": "第一单元",
  "lessons": [
    {
      "lesson": 1,
      "title": "古诗三首",
      "words": [
        "优惠","惠及","融化","融合","燕子","燕麦",
        "崇高","崇敬","豆芽","发芽","梅花","广泛",
        "剑法","杨梅","萌芽","宽泛","泛舟",
        "减轻","减速","冰雪消融","鸳鸯戏水"
      ]
    },
    {
      "lesson": 2,
      "title": "燕子",
      "words": [
        "燕子","乌黑","剪刀","活泼","轻风","洒落","赶集",
        "光彩夺目","春光","偶尔","闲散","纤细","电线",
        "凑近","凑齐","集合","沾光","泼落",
        "玩偶","尔后","休闲","化纤","拉杆",
        "空闲","沾边","光彩夺目","沾沾自喜"
      ]
    },
    {
      "lesson": 3,
      "title": "荷花",
      "words": [
        "荷花","公园","清香","赶紧","荷叶","莲蓬","破裂",
        "姿势","画家","本领","了不起","微风","停止",
        "荷塘","蓬松","紧密","微风","断裂","挨近","紧挨",
        "势力","忘记","摘记","饱胀","鼓胀",
        "轻微","微妙","了不起","挨挨挤挤"
      ]
    },
    {
      "lesson": 0,
      "title": "语文园地一",
      "words": [
        "匕首","乙方","冗长","军犬","兑换","争执",
        "回忆","记忆","艺术","手艺","冗长","军犬",
        "兑换","兑现","争执","执行","清仓","关税","税收"
      ]
    }
  ]
};

// 替换第一单元
data.grades[idx].units[0] = newUnit1;

// 统计
const totalU1 = newUnit1.lessons.reduce((s, l) => s + l.words.length, 0);
console.log('\n=== 第一单元（更新后）===');
newUnit1.lessons.forEach(l => {
  console.log(`  第${l.lesson || '园地'}课 ${l.title}: ${l.words.length}词`);
  console.log(`    → ${l.words.join(' ')}`);
});
console.log(`\n  第一单元总计: ${totalU1} 个词`);

// 统计全册
let totalAll = 0;
data.grades[idx].units.forEach(u => {
  const wc = u.lessons.reduce((s, l) => s + l.words.length, 0);
  totalAll += wc;
});
console.log(`  三年级下册总计: ${data.grades[idx].units.length}个单元, ${totalAll}个词`);

fs.writeFileSync(filePath, JSON.stringify(data), 'utf-8');
console.log('\n✅ 第一单元已更新！');
