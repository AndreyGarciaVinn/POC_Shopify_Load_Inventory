import os
import requests
from dotenv import load_dotenv
from typing import Dict, List, Optional

load_dotenv()

class ShopifyInventoryManager:
    def __init__(self):
        self.shop_domain = os.getenv('SHOPIFY_SHOP_DOMAIN')
        self.access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.api_version = os.getenv('SHOPIFY_API_VERSION', '2024-07')
        self.base_url = f"https://{self.shop_domain}/admin/api/{self.api_version}/graphql.json"
        
        if not self.shop_domain or not self.access_token:
            raise ValueError("SHOPIFY_SHOP_DOMAIN y SHOPIFY_ACCESS_TOKEN son requeridos en el archivo .env")
    
    def _make_request(self, query: str, variables: Dict = None) -> Dict:
        """Realizar peticion GraphQL a Shopify (factory)"""
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.access_token
        }
        
        payload = {
            'query': query,
            'variables': variables or {}
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error en la petición: {e}")
            return None
    
    def get_locations(self) -> List[Dict]:
        """Obtener todas las ubicaciones de la tienda"""
        query = """
        query getLocations {
          locations(first: 50) {
            edges {
              node {
                id
                name
                address {
                  city
                  country
                }
              }
            }
          }
        }
        """
        
        result = self._make_request(query)
        if result and 'data' in result:
            locations = []
            for edge in result['data']['locations']['edges']:
                location = edge['node']
                locations.append({
                    'id': location['id'].split('/')[-1],  # Extraer solo el ID (numero)
                    'gid': location['id'],  # ID completo
                    'name': location['name'],
                    'city': location.get('address', {}).get('city', 'N/A')
                })
            return locations
        return []
    
    def get_product_inventory_items(self, product_handle: str = None, sku: str = None) -> List[Dict]:
        """Obtener inventory items de un producto por handle o SKU"""
        if product_handle:
            query = """
            query getProductByHandle($handle: String!) {
              productByHandle(handle: $handle) {
                id
                title
                variants(first: 50) {
                  edges {
                    node {
                      id
                      sku
                      inventoryItem {
                        id
                      }
                    }
                  }
                }
              }
            }
            """
            variables = {'handle': product_handle}
        elif sku:
            query = """
            query getProductVariantBySku($query: String!) {
              productVariants(first: 10, query: $query) {
                edges {
                  node {
                    id
                    sku
                    product {
                      id
                      title
                    }
                    inventoryItem {
                      id
                    }
                  }
                }
              }
            }
            """
            variables = {'query': f'sku:{sku}'}
        else:
            raise ValueError("Debes proporcionar product_handle o sku") # xd
        
        result = self._make_request(query, variables)
        if not result or 'data' not in result:
            return []
        
        inventory_items = []
        
        if product_handle:
            product = result['data']['productByHandle']
            if product:
                for edge in product['variants']['edges']:
                    variant = edge['node']
                    inventory_items.append({
                        'variant_id': variant['id'].split('/')[-1],
                        'sku': variant['sku'],
                        'inventory_item_id': variant['inventoryItem']['id'].split('/')[-1],
                        'inventory_item_gid': variant['inventoryItem']['id'],
                        'product_title': product['title']
                    })
        else:  # per SKU
            for edge in result['data']['productVariants']['edges']:
                variant = edge['node']
                inventory_items.append({
                    'variant_id': variant['id'].split('/')[-1],
                    'sku': variant['sku'],
                    'inventory_item_id': variant['inventoryItem']['id'].split('/')[-1],
                    'inventory_item_gid': variant['inventoryItem']['id'],
                    'product_title': variant['product']['title']
                })
        
        return inventory_items
    
    def get_inventory_levels(self, inventory_item_id: str) -> List[Dict]:
        """Obtener niveles de inventario actuales para un inventory item"""
        query = """
        query getInventoryLevels($inventoryItemId: ID!) {
          inventoryItem(id: $inventoryItemId) {
            id
            sku
            inventoryLevels(first: 50) {
              edges {
                node {
                  id
                  available
                  location {
                    id
                    name
                  }
                }
              }
            }
          }
        }
        """
        
        # Asegurar que tenemos el GID completo
        if not inventory_item_id.startswith('gid://'):
            inventory_item_id = f"gid://shopify/InventoryItem/{inventory_item_id}"
        
        variables = {'inventoryItemId': inventory_item_id}
        
        result = self._make_request(query, variables)
        if not result or 'data' not in result or not result['data']['inventoryItem']:
            return []
        
        levels = []
        for edge in result['data']['inventoryItem']['inventoryLevels']['edges']:
            level = edge['node']
            levels.append({
                'location_id': level['location']['id'].split('/')[-1],
                'location_gid': level['location']['id'],
                'location_name': level['location']['name'],
                'available': level['available']
            })
        
        return levels
    
    def update_inventory(self, inventory_item_id: str, location_id: str, quantity_change: int, reason: str = "correction") -> bool:
        """
        Actualizar inventario
        
        Args:
            inventory_item_id: ID del inventory item
            location_id: ID de la ubicacion
            quantity_change: Cantidad a agregar (positivo) o quitar (negativo)
            reason: Razón del ajuste ("correction", "cycle_count", "damaged", etc.)
        """
        mutation = """
        mutation inventoryAdjustQuantities($input: InventoryAdjustQuantitiesInput!) {
          inventoryAdjustQuantities(input: $input) {
            inventoryAdjustmentGroup {
              reason
              changes {
                name
                delta
              }
            }
            userErrors {
              field
              message
            }
          }
        }
        """
        
        # Asegurar que tenemos los GIDs completos
        if not inventory_item_id.startswith('gid://'):
            inventory_item_id = f"gid://shopify/InventoryItem/{inventory_item_id}"
        
        if not location_id.startswith('gid://'):
            location_id = f"gid://shopify/Location/{location_id}"
        
        variables = {
            "input": {
                "reason": reason,
                "name": "available",
                "changes": [
                    {
                        "delta": quantity_change,
                        "inventoryItemId": inventory_item_id,
                        "locationId": location_id
                    }
                ]
            }
        }
        
        result = self._make_request(mutation, variables)
        
        if not result or 'data' not in result:
            print("Error: No se pudo procesar la petición")
            return False
        
        adjust_result = result['data']['inventoryAdjustQuantities']
        
        if adjust_result['userErrors']:
            print("Errores al actualizar inventario:")
            for error in adjust_result['userErrors']:
                print(f"  - {error['field']}: {error['message']}")
            return False
        
        print(" Inventario actualizado exitosamente")
        if adjust_result['inventoryAdjustmentGroup']:
            changes = adjust_result['inventoryAdjustmentGroup']['changes']
            for change in changes:
                print(f"   Cambio en {change['name']}: {change['delta']}")
        
        return True
    
    def set_inventory_quantity(self, inventory_item_id: str, location_id: str, new_quantity: int) -> bool:
        """
        Establecer inventario
        """
        # Primero obtener la cantidad actual
        current_levels = self.get_inventory_levels(inventory_item_id)
        
        current_quantity = 0
        for level in current_levels:
            if level['location_id'] == location_id or level['location_gid'] == location_id:
                current_quantity = level['available']
                break
        
        quantity_change = new_quantity - current_quantity
        
        if quantity_change == 0:
            print(f"La cantidad actual ya es {new_quantity}")
            return True
        
        print(f"Cantidad actual: {current_quantity}")
        print(f"Nueva cantidad: {new_quantity}")
        print(f"Cambio necesario: {quantity_change}")
        
        return self.update_inventory(inventory_item_id, location_id, quantity_change)
    

    def get_all_inventory_by_location(self, location_id: str, limit: int = 250) -> List[Dict]:
        """
        Obtener TODO el inventario de una ubicación específica
        
        Args:
            location_id: ID de la unicacion o warehouse
            limit: Cantidad máxima de items por consulta (250 max !TODO: testear con menos para procesamiento por hilos)
        """
        query = """
        query getInventoryByLocation($locationId: ID!, $first: Int!, $after: String) {
          location(id: $locationId) {
            id
            name
            inventoryLevels(first: $first, after: $after) {
              edges {
                node {
                  id
                  quantities(names: ["available", "on_hand", "committed", "incoming", "reserved"]) {
                    name
                    quantity
                  }
                  item {
                    id
                    sku
                    tracked
                  }
                }
              }
              pageInfo {
                hasNextPage
                endCursor
              }
            }
          }
        }
        """
        
        # Asegurar que tenemos el GID completo
        if not location_id.startswith('gid://'):
            location_id = f"gid://shopify/Location/{location_id}"
        
        all_inventory = []
        cursor = None
        has_next_page = True
        
        while has_next_page:
            variables = {
                'locationId': location_id,
                'first': min(limit, 250),  # 25 max
                'after': cursor
            }
            
            result = self._make_request(query, variables)
            
            if not result or 'data' not in result or not result['data']['location']:
                break
            
            location_data = result['data']['location']
            inventory_levels = location_data['inventoryLevels']
            
            for edge in inventory_levels['edges']:
                item = edge['node']
                
                quantities_dict = {q['name']: q['quantity'] for q in item['quantities']}
                available_qty = quantities_dict.get('available', 0)
                
                inventory_item = {
                    'inventory_level_id': item['id'].split('/')[-1] if '?' in item['id'] else item['id'].split('/')[-1],
                    'inventory_level_gid': item['id'],
                    'available': available_qty,
                    'inventory_item_id': item['item']['id'].split('/')[-1],
                    'inventory_item_gid': item['item']['id'],
                    'sku': item['item']['sku'],
                    'tracked': item['item']['tracked'],
                    'location_name': location_data['name'],
                    'quantities': quantities_dict,
                }
                
                all_inventory.append(inventory_item)
            
            # paginacion
            page_info = inventory_levels['pageInfo']
            has_next_page = page_info['hasNextPage']
            cursor = page_info.get('endCursor')
            
            print(f"Cargados {len(all_inventory)} items de inventario")
        
        print(f" Total de items de inventario obtenidos: {len(all_inventory)}")
        return all_inventory
    
    def get_inventory_with_product_info(self, location_id: str, limit: int = 50) -> List[Dict]:
        """
        Obtener inventario de una ubicación CON información de productos
        Usa una query diferente que va desde productos hacia inventario
        """
        query = """
        query getProductsWithInventory($locationId: ID!, $first: Int!, $after: String) {
          products(first: $first, after: $after) {
            edges {
              node {
                id
                title
                handle
                variants(first: 50) {
                  edges {
                    node {
                      id
                      title
                      sku
                      price
                      inventoryItem {
                        id
                        tracked
                        inventoryLevel(locationId: $locationId) {
                          id
                          quantities(names: ["available", "on_hand", "committed"]) {
                            name
                            quantity
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """
        
        # Asegurar que tenemos el GID completo
        if not location_id.startswith('gid://'):
            location_id = f"gid://shopify/Location/{location_id}"
        
        all_inventory = []
        cursor = None
        has_next_page = True
        
        while has_next_page:
            variables = {
                'locationId': location_id,
                'first': min(limit, 50),  # testenado 50, el maximo es 250 !TODO: TESTEAR CON MAXIMOS
                'after': cursor
            }
            
            result = self._make_request(query, variables)
            
            if not result or 'data' not in result:
                break
            
            products = result['data']['products']
            
            for product_edge in products['edges']:
                product = product_edge['node']
                
                for variant_edge in product['variants']['edges']:
                    variant = variant_edge['node']
                    inventory_item = variant['inventoryItem']
                    
                    if inventory_item and inventory_item.get('inventoryLevel'):
                        inventory_level = inventory_item['inventoryLevel']
                        quantities_dict = {q['name']: q['quantity'] for q in inventory_level['quantities']}
                        available_qty = quantities_dict.get('available', 0)
                        
                        inventory_record = {
                            'inventory_level_id': inventory_level['id'].split('/')[-1] if '?' in inventory_level['id'] else inventory_level['id'].split('/')[-1],
                            'inventory_level_gid': inventory_level['id'],
                            'available': available_qty,
                            'inventory_item_id': inventory_item['id'].split('/')[-1],
                            'inventory_item_gid': inventory_item['id'],
                            'sku': variant['sku'],
                            'tracked': inventory_item['tracked'],
                            'quantities': quantities_dict,
                            # Información adicional del producto
                            'product_id': product['id'].split('/')[-1],
                            'product_title': product['title'],
                            'product_handle': product['handle'],
                            'variant_id': variant['id'].split('/')[-1],
                            'variant_title': variant['title'],
                            'variant_price': variant['price'],
                        }
                        
                        all_inventory.append(inventory_record)
            
            # paginacion
            page_info = products['pageInfo']
            has_next_page = page_info['hasNextPage']
            cursor = page_info.get('endCursor')
            
            print(f"Procesados {len(all_inventory)} items con información de producto...")
        
        print(f" Total de items con información de producto: {len(all_inventory)}")
        return all_inventory
    
    def get_inventory_summary_by_location(self, location_id: str) -> Dict:
        """
        Total de una locacion
        """
        inventory_items = self.get_all_inventory_by_location(location_id)
        
        if not inventory_items:
            return {}
        
        total_items = len(inventory_items)
        items_with_stock = len([item for item in inventory_items if item['available'] > 0])
        total_available = sum(item['available'] for item in inventory_items)
        total_on_hand = sum(item['quantities'].get('on_hand', 0) for item in inventory_items)
        total_committed = sum(item['quantities'].get('committed', 0) for item in inventory_items)
        total_incoming = sum(item['quantities'].get('incoming', 0) for item in inventory_items)
        
        return {
            'location_name': inventory_items[0]['location_name'] if inventory_items else 'Unknown',
            'total_items': total_items,
            'items_with_stock': items_with_stock,
            'items_out_of_stock': total_items - items_with_stock,
            'total_available': total_available,
            'total_on_hand': total_on_hand,
            'total_committed': total_committed,
            'total_incoming': total_incoming,
            'stock_percentage': round((items_with_stock / total_items) * 100, 2) if total_items > 0 else 0
        }