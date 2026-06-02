import { StyleSheet, Switch, Text, View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { Drawer } from 'expo-router/drawer';
import { DrawerContentScrollView, DrawerItemList } from '@react-navigation/drawer';
import { Ionicons } from '@expo/vector-icons';
import { ThemeProvider, useTheme } from '../src/theme';

function CustomDrawerContent(props: any) {
  const { theme, isDark, toggleTheme } = useTheme();
  const c = theme.colors;
  return (
    <View style={{ flex: 1, backgroundColor: c.drawerBg }}>
      {/* Branding header */}
      <View style={[styles.brandHeader, { borderBottomColor: c.border }]}>
        <View style={[styles.brandIcon, { backgroundColor: c.accent }]}>
          <Ionicons name="sparkles" size={20} color="#ffffff" />
        </View>
        <View style={styles.brandText}>
          <Text style={[styles.brandName, { color: c.text }]}>DocChat</Text>
          <Text style={[styles.brandSub, { color: c.textMuted }]}>AI Document Assistant</Text>
        </View>
      </View>

      <DrawerContentScrollView {...props} style={{ backgroundColor: c.drawerBg }}>
        <DrawerItemList {...props} />
      </DrawerContentScrollView>

      <View style={[styles.toggleRow, { borderTopColor: c.border, backgroundColor: c.drawerBg }]}>
        <View style={styles.toggleLeft}>
          <Ionicons
            name={isDark ? 'moon' : 'sunny-outline'}
            size={20}
            color={c.accent}
            style={{ marginRight: 12 }}
          />
          <Text style={[styles.toggleLabel, { color: c.text }]}>Dark Mode</Text>
        </View>
        <Switch
          value={isDark}
          onValueChange={toggleTheme}
          trackColor={{ false: '#767577', true: c.accent }}
          thumbColor="#ffffff"
        />
      </View>
    </View>
  );
}

function ThemedDrawer() {
  const { theme } = useTheme();
  const c = theme.colors;
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: c.background }}>
      <Drawer
        drawerContent={(props) => <CustomDrawerContent {...props} />}
        screenOptions={{
          headerStyle: { backgroundColor: c.headerBg },
          headerTintColor: c.text,
          headerTitleStyle: { fontWeight: '700', fontSize: 17 },
          headerShadowVisible: false,
          drawerStyle: { backgroundColor: c.drawerBg, width: 280 },
          drawerActiveTintColor: c.accent,
          drawerInactiveTintColor: c.textMuted,
          drawerActiveBackgroundColor: c.drawerActiveBg,
          drawerItemStyle: { borderRadius: 10, marginHorizontal: 8 },
          drawerLabelStyle: { fontWeight: '600', fontSize: 15 },
        }}
      >
        <Drawer.Screen
          name="index"
          options={{
            title: 'Chat',
            drawerIcon: ({ color, size }) => (
              <Ionicons name="chatbubbles-outline" size={size} color={color} />
            ),
          }}
        />
        <Drawer.Screen
          name="expenses"
          options={{
            title: 'Expenses',
            drawerIcon: ({ color, size }) => (
              <Ionicons name="wallet-outline" size={size} color={color} />
            ),
          }}
        />
        <Drawer.Screen
          name="exercises"
          options={{
            title: 'Exercises',
            drawerIcon: ({ color, size }) => (
              <Ionicons name="barbell-outline" size={size} color={color} />
            ),
          }}
        />
        <Drawer.Screen
          name="files"
          options={{
            title: 'Files',
            drawerIcon: ({ color, size }) => (
              <Ionicons name="document-text-outline" size={size} color={color} />
            ),
          }}
        />
      </Drawer>
    </GestureHandlerRootView>
  );
}

export default function RootLayout() {
  return (
    <ThemeProvider>
      <ThemedDrawer />
    </ThemeProvider>
  );
}

const styles = StyleSheet.create({
  brandHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 56,
    paddingBottom: 20,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 14,
  },
  brandIcon: {
    width: 42,
    height: 42,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  brandText: {
    flex: 1,
  },
  brandName: {
    fontSize: 18,
    fontWeight: '700',
    letterSpacing: -0.3,
  },
  brandSub: {
    fontSize: 12,
    marginTop: 1,
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  toggleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  toggleLabel: {
    fontSize: 15,
    fontWeight: '500',
  },
});
