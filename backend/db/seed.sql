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

-- Give seeded (and any legacy) products a one-item gallery from their primary image.
update products set images = jsonb_build_array(image_url)
  where (images is null or images = '[]'::jsonb) and coalesce(image_url, '') <> '';

-- Default delivery settings (Abu Dhabi/Al Ain = 30, rest = 25, free over 250).
insert into settings (key, value)
select 'delivery', '{"fee_high": 30, "fee_low": 25, "free_threshold": 250}'::jsonb
where not exists (select 1 from settings where key = 'delivery');

-- Seed the four "why us" value cards (only when the table is empty).
insert into content_values (sort, image_url, link, title_ar, title_en, desc_ar, desc_en, more_ar, more_en)
select * from (values
  (1, '/images/badge-asli.png', '#pantry',
   'منتجاتٌ أصليّة', 'Authentic products',
   'من مصادرها مباشرةً، بلا وسطاء', 'Straight from the source, no middlemen',
   'نتعامل مباشرةً مع المزارعين والحِرفيّين الفلسطينيّين بلا وسطاء، وكلّ صنفٍ موثَّقُ المصدر والمنشأ.', 'We deal directly with Palestinian farmers and artisans with no middlemen, and every item has a documented source and origin.'),
  (2, '/images/badge-ard.png', '#story',
   'من أرض فلسطين', 'From the land of Palestine',
   'حصادٌ وحِرفةٌ من القرى', 'Harvest and craft from the villages',
   'مونتنا من قرى الضفّة وحقولها، وخزفنا من أفران الخليل العتيقة. أصلٌ واحدٌ لا يتبدّل.', 'Our mouneh comes from the villages and fields of the West Bank, and our ceramics from the old kilns of Hebron. One unchanging origin.'),
  (3, '/images/badge-jawda.png', '#pantry',
   'جودةٌ عالية', 'High quality',
   'طبيعيٌّ بلا إضافاتٍ حافظة', 'Natural, no preservatives',
   'بلا موادَّ حافظةٍ أو إضافات. نفحص كلّ دفعةٍ يدويًّا قبل أن تصل إليك طازجةً كما يجب.', 'No preservatives or additives. We inspect every batch by hand before it reaches you, fresh as it should be.'),
  (4, '/images/badge-tawsil.png', '#contact',
   'توصيلٌ سريع', 'Fast delivery',
   'يصل طازجًا إلى بابك', 'Arrives fresh at your door',
   'نشحن خلال 24–48 ساعة داخل دولة الإمارات، وشحنٌ مجّانيٌّ لكلّ طلبٍ تتجاوز قيمته 250 درهمًا.', 'We ship within 24-48 hours inside the UAE, with free shipping on every order above 250 dirham.')
) as v(sort, image_url, link, title_ar, title_en, desc_ar, desc_en, more_ar, more_en)
where not exists (select 1 from content_values);
