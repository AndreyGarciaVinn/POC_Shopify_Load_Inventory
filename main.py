from services.Shopify_Inventory import ShopifyInventoryManager
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def main():
    """Ejemplo de uso"""
    try:
        manager = ShopifyInventoryManager()
        
        # 1. Obtener ubicaciones
        print("Ubicaciones disponibles:")
        locations = manager.get_locations()
        for location in locations:
            print(f"  - {location['name']} (ID: {location['id']}) - {location['city']}")
    
        use_Location                = locations[1]['gid'] # La unica que tiene inventario
        location_Invetory_Summary   = manager.get_inventory_summary_by_location(use_Location)
        location_Inventory_Detailed = manager.get_inventory_with_product_info(use_Location)

        # print(f"Inventario de {location_Invetory_Summary}:")
        # print(json.dumps(location_Inventory_Detailed, indent=4)) # los acentos se ven raros (no lo cambiare a utf-8)
        start_Time = time.time()

        # Sincrono 

        # for item in location_Inventory_Detailed:
        #     added_quantity = random.randint(0, 100)
        #     print(f"""
        #         * SKU {item['sku']}
        #         * Actualizando {item['inventory_item_id']}
        #         * Stock actual: {item['available']}
        #         * Sumando: {added_quantity}
        #     """)
        #     manager.set_inventory_quantity(item['inventory_item_id'], use_Location, added_quantity)

        # Asincrono con ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = []
            for item in location_Inventory_Detailed:
                added_quantity = random.randint(0, 100)
                print(f"""
                    * SKU {item['sku']}
                    * Actualizando {item['inventory_item_id']}
                    * Stock actual: {item['available']}
                    * Sumando: {added_quantity}
                """)
                futures.append(executor.submit(manager.set_inventory_quantity, item['inventory_item_id'], use_Location, added_quantity))
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    print(f"Resultado de la actualización: {result}")
                except Exception as e:
                    print(f"Error al actualizar inventario: {e}")

        end_Time = time.time()
        print(f"Tiempo total para actualizar inventario: {end_Time - start_Time:.2f} segundos")

    except Exception as e:
        print(f"i really hts: ", e)


if __name__ == "__main__":
    main()