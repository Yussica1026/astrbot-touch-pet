import ActivityKit
import SwiftUI
import WidgetKit

struct TouchPetLiveActivityWidget: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: TouchPetAttributes.self) { context in
            HStack(spacing: 12) {
                Text(context.attributes.symbol).font(.system(size: 34))
                VStack(alignment: .leading) {
                    Text(context.attributes.petName).font(.headline)
                    Text(context.state.lastGesture ?? context.state.status).font(.caption)
                }
                Spacer()
                Button(intent: SendTouchIntent(gesture: "tap")) { Image(systemName: "hand.tap") }
                    .buttonStyle(.borderedProminent)
                Button(intent: SendTouchIntent(gesture: "long_press")) { Image(systemName: "hand.raised") }
                    .buttonStyle(.bordered)
            }
            .padding()
            .activityBackgroundTint(Color.indigo.opacity(0.25))
            .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Text(context.attributes.symbol).font(.title)
                }
                DynamicIslandExpandedRegion(.center) {
                    Text(context.state.lastGesture ?? context.state.status).font(.caption)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    HStack {
                        Button(intent: SendTouchIntent(gesture: "tap")) { Label("轻戳", systemImage: "hand.tap") }
                        Button(intent: SendTouchIntent(gesture: "long_press")) { Label("摸摸", systemImage: "hand.raised") }
                        Button(intent: SendTouchIntent(gesture: "double_tap")) { Label("戳两下", systemImage: "hand.tap.fill") }
                    }
                    .font(.caption)
                }
            } compactLeading: {
                Text(context.attributes.symbol)
            } compactTrailing: {
                Image(systemName: context.state.lastGesture == nil ? "heart" : "checkmark.circle.fill")
            } minimal: {
                Text(context.attributes.symbol)
            }
            .keylineTint(.indigo)
        }
    }
}

