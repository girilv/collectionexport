import os
import sqlite3
import json
import shutil
from datetime import datetime
from pathlib import Path

class EdgeCollectionsExporter:
    def __init__(self):
        self.edge_collections_path = os.path.join(
            os.environ['LOCALAPPDATA'],
            'Microsoft', 'Edge', 'User Data', 'Default', 'Collections', 'collectionsSQLite'
        )
        self.chrome_bookmarks_path = os.path.join(
            os.environ['LOCALAPPDATA'],
            'Google', 'Chrome', 'User Data', 'Default', 'Bookmarks'
        )

    def read_edge_collections(self):
        """Read collections from Edge SQLite database"""
        if not os.path.exists(self.edge_collections_path):
            raise FileNotFoundError(f"Edge Collections database not found at: {self.edge_collections_path}")

        # Create a temporary copy to avoid locking issues
        temp_db = 'temp_collections.db'
        shutil.copy2(self.edge_collections_path, temp_db)

        try:
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()

            # Get all collections
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"Available tables: {tables}")

            # Try to find collections and items
            collections = {}

            # Common table names in Edge Collections
            try:
                cursor.execute("SELECT * FROM collections")
                collections_data = cursor.fetchall()
                cursor.execute("PRAGMA table_info(collections)")
                collections_columns = [col[1] for col in cursor.fetchall()]

                cursor.execute("SELECT * FROM items")
                items_data = cursor.fetchall()
                cursor.execute("PRAGMA table_info(items)")
                items_columns = [col[1] for col in cursor.fetchall()]

                print(f"\nCollections columns: {collections_columns}")
                print(f"Collections data: {collections_data[:3]}")  # Show first 3

                print(f"\nItems columns: {items_columns}")
                print(f"Items data: {items_data[:3]}")  # Show first 3

                # Parse collections
                for collection_row in collections_data:
                    collection_dict = dict(zip(collections_columns, collection_row))
                    collection_id = collection_dict.get('collection_id') or collection_dict.get('id')
                    collection_name = collection_dict.get('title') or collection_dict.get('name', 'Unnamed Collection')

                    collections[collection_id] = {
                        'name': collection_name,
                        'items': []
                    }

                # Check columns in relationship table
                cursor.execute("PRAGMA table_info(collections_items_relationship)")
                rel_columns = [col[1] for col in cursor.fetchall()]
                print(f"\nRelationship table columns: {rel_columns}")

                # Parse items using JOIN query (as per open-source project)
                item_count = 0

                print("\nExtracting items for each collection...")
                for collection_id, collection_data in collections.items():
                    # Use the correct query with parent_id from the open-source project
                    query = """
                        SELECT items.title, items.source, items.date_created
                        FROM collections_items_relationship
                        JOIN items ON (collections_items_relationship.item_id = items.id)
                        WHERE collections_items_relationship.parent_id = ?
                        AND items.type = 'website'
                    """

                    cursor.execute(query, (collection_id,))
                    collection_items = cursor.fetchall()

                    for item_row in collection_items:
                        title, source_blob, date_created = item_row

                        # Extract URL from source JSON
                        url = ''
                        if source_blob:
                            try:
                                source_json = json.loads(source_blob.decode('utf-8') if isinstance(source_blob, bytes) else source_blob)
                                url = source_json.get('url', '')
                            except Exception as e:
                                print(f"Error parsing source: {e}")
                                continue

                        if url:
                            item = {
                                'title': title or 'Untitled',
                                'url': url,
                                'date_added': date_created
                            }
                            collection_data['items'].append(item)
                            item_count += 1

                print(f"Total items extracted: {item_count}")
                print(f"\nBreakdown by collection:")
                for coll_id, coll_data in collections.items():
                    if len(coll_data['items']) > 0:
                        print(f"  - {coll_data['name']}: {len(coll_data['items'])} items")

            except sqlite3.OperationalError as e:
                print(f"Error reading standard schema: {e}")
                print("\nTrying alternative approach...")

                # Dump all table structures for debugging
                for table in tables:
                    table_name = table[0]
                    try:
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        columns = cursor.fetchall()
                        print(f"\nTable: {table_name}")
                        print(f"Columns: {columns}")

                        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                        sample_data = cursor.fetchall()
                        print(f"Sample data: {sample_data}")
                    except Exception as e:
                        print(f"Error reading table {table_name}: {e}")

            conn.close()
            return collections

        finally:
            # Clean up temp database
            if os.path.exists(temp_db):
                os.remove(temp_db)

    def create_html_bookmarks(self, collections):
        """Create HTML bookmarks file from Edge collections"""
        html_parts = []

        # HTML header
        html_parts.append('<!DOCTYPE NETSCAPE-Bookmark-file-1>')
        html_parts.append('<!-- This is an automatically generated file.')
        html_parts.append('     It will be read and overwritten.')
        html_parts.append('     DO NOT EDIT! -->')
        html_parts.append('<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">')
        html_parts.append('<TITLE>Bookmarks</TITLE>')
        html_parts.append('<H1>Bookmarks</H1>')
        html_parts.append('<DL><p>')

        # Add collections as folders
        for collection_id, collection_data in collections.items():
            collection_name = collection_data['name']
            html_parts.append(f'    <DT><H3>{collection_name}</H3>')
            html_parts.append('    <DL><p>')

            # Add items to folder
            for item in collection_data['items']:
                if item['url']:  # Only add items with URLs
                    title = item['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    url = item['url']
                    html_parts.append(f'        <DT><A HREF="{url}">{title}</A>')

            html_parts.append('    </DL><p>')

        html_parts.append('</DL><p>')

        return '\n'.join(html_parts)

    def export_to_chrome(self, output_path=None):
        """Main export function"""
        print("Reading Edge Collections...")
        collections = self.read_edge_collections()

        if not collections:
            print("No collections found!")
            return

        print(f"\nFound {len(collections)} collection(s)")
        for coll_id, coll_data in collections.items():
            print(f"  - {coll_data['name']}: {len(coll_data['items'])} items")

        print("\nCreating HTML bookmarks file...")
        html_bookmarks = self.create_html_bookmarks(collections)

        # Determine output path
        if output_path is None:
            output_path = 'chrome_bookmarks_import.html'

        print(f"\nExporting to: {output_path}")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_bookmarks)

        print("\n✓ Export completed successfully!")
        print(f"\nTo import into Chrome:")
        print(f"1. Open Chrome and press Ctrl+Shift+O (or go to chrome://bookmarks/)")
        print(f"2. Click the three dots menu (⋮) in the top right")
        print(f"3. Select 'Import bookmarks'")
        print(f"4. Choose the file: {os.path.abspath(output_path)}")

        return output_path

def main():
    exporter = EdgeCollectionsExporter()

    try:
        exporter.export_to_chrome()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nPlease make sure Microsoft Edge is installed and you have created some Collections.")
    except Exception as e:
        print(f"Error during export: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
