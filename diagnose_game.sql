-- Diagnose what is blocking deletion of a specific game.
-- Usage: psql -h <host> -U <user> -d sharewarez -v uuid="'3b2a3bcf-d296-47a9-b2d4-cdb9e29b60c8'" -f diagnose_game.sql

\set g :uuid

select 'game row' as what, uuid, name, full_disk_path, library_uuid
from games where uuid = :g;

select 'referencing rows' as what, tbl, n from (
  select 'images'                              as tbl, count(*) as n from images                where game_uuid = :g
  union all select 'game_urls',                       count(*) from game_urls                   where game_uuid = :g
  union all select 'game_updates',                    count(*) from game_updates                where game_uuid = :g
  union all select 'game_extras',                     count(*) from game_extras                 where game_uuid = :g
  union all select 'user_favorites',                  count(*) from user_favorites              where game_uuid = :g
  union all select 'user_game_status',                count(*) from user_game_status            where game_uuid = :g
  union all select 'download_requests',                count(*) from download_requests           where game_uuid = :g
  union all select 'game_developer_association',      count(*) from game_developer_association  a join games gm on gm.id = a.game_id where gm.uuid = :g
  union all select 'game_genre_association',          count(*) from game_genre_association      a join games gm on gm.id = a.game_id where gm.uuid = :g
  union all select 'game_platform_association',       count(*) from game_platform_association   a join games gm on gm.id = a.game_id where gm.uuid = :g
  union all select 'game_theme_association',          count(*) from game_theme_association      a join games gm on gm.id = a.game_id where gm.uuid = :g
  union all select 'game_game_mode_association',      count(*) from game_game_mode_association  a join games gm on gm.id = a.game_id where gm.uuid = :g
  union all select 'game_player_perspective_association', count(*) from game_player_perspective_association a join games gm on gm.id = a.game_id where gm.uuid = :g
  union all select 'game_multiplayer_mode_association',   count(*) from game_multiplayer_mode_association   a join games gm on gm.id = a.game_id where gm.uuid = :g
) s where n > 0 order by tbl;
