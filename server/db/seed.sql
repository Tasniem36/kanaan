-- Seed products (idempotent-ish: only inserts when the table is empty).
insert into products (name, description, price, unit, category, tag, image_url, stock)
select * from (values
  ('زيت زيتون بكر ممتاز', 'عصرةٌ أولى على البارد من حصاد هذا الموسم.', 65::numeric, 'لتر', 'pantry'::product_category, 'حصاد جديد', '/images/oil.jpg', 40),
  ('زعتر فلسطيني بلدي', 'زعترٌ مجفّفٌ مع سمسمٍ محمّصٍ وسمّاق.', 28, '400غ', 'pantry', 'الأكثر مبيعًا', '/images/zaatar.jpg', 60),
  ('لبنة بلديّة بحبّة البركة', 'لبنةٌ مصفّاةٌ مزيّنةٌ بحبّة البركة وزيت الزيتون.', 35, '500غ', 'pantry', null, '/images/labneh.jpg', 35),
  ('جبنة بيضاء بلديّة', 'جبنةٌ طريّةٌ من حليبٍ طازج، مالحةٌ باعتدال.', 38, '500غ', 'pantry', null, '/images/cheese.jpg', 4),
  ('زيتون مكسّر بالليمون', 'زيتونٌ أخضر بلديٌّ بالثوم والليمون.', 30, '500غ', 'pantry', null, '/images/olives.jpg', 50),
  ('إبريق فخّار خليلي', 'مزخرفٌ يدويًّا بنقوشٍ نباتيّة، يحفظ الماء باردًا.', 120, 'قطعة', 'pottery', 'يدويّ', '/images/jug.jpg', 3),
  ('طقم فناجين خزف', 'فناجين بنقشٍ خليليٍّ تقليديٍّ للضيافة.', 140, 'طقم', 'pottery', null, '/images/cups.jpg', 12),
  ('زبديّة خزف مزخرفة', 'للتقديم أو للزينة، بنقوشٍ خضراء أنيقة.', 75, 'قطعة', 'pottery', null, '/images/bowl.jpg', 20)
) as v(name, description, price, unit, category, tag, image_url, stock)
where not exists (select 1 from products);
