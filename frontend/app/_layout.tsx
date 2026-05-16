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
      <DrawerContentScrollView {...props} style={{ backgroundColor: c.drawerBg }}>
        <DrawerItemList {...props} />
      </DrawerContentScrollView>

      <View style={[styles.toggleRow, { borderTopColor: c.border, backgroundColor: c.drawerBg }]}>
        <View style={styles.toggleLeft}>
          <Ionicons
            name={isDark ? 'moon' : 'sunny-outline'}
            size={20}
            color={c.textMuted}
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
          headerTintColor: '#ffffff',
          headerTitleStyle: { fontWeight: '600' },
          drawerStyle: { backgroundColor: c.drawerBg },
          drawerActiveTintColor: c.accent,
          drawerInactiveTintColor: c.textMuted,
          drawerActiveBackgroundColor: c.drawerActiveBg,
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
  },
});
